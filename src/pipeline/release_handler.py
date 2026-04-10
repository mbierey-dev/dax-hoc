import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from db import get_session
from db.models import (
    Company,
    EarningsEvent,
    ExpectationsSnapshot,
    NewsItem,
    TradeDecision,
)
from earnings.matcher import find_matching_event, is_earnings_news
from earnings.time_estimator import estimate_release_time
from ensemble.pipeline import run as run_ensemble

logger = logging.getLogger(__name__)


def handle_news_item(news_item: NewsItem, engine) -> TradeDecision | None:
    """
    Try to match a news item to a scheduled earnings event and run the full ensemble.
    Returns the TradeDecision if a match is found, else None.
    """
    if not is_earnings_news(news_item):
        return None

    event = find_matching_event(news_item, engine)
    if not event:
        return None

    session = get_session(engine)
    try:
        company = session.get(Company, event.isin)
        if not company:
            logger.warning("No company row for ISIN %s", event.isin)
            return None

        snapshot = session.scalars(
            select(ExpectationsSnapshot).where(
                ExpectationsSnapshot.earnings_event_id == event.id
            )
        ).first()

        # Mark event released and link to this news item
        event.status = "released"
        event.actual_release_at = news_item.created_at_utc or datetime.now(timezone.utc)
        event.news_item_id = news_item.id

        # Update time-of-day estimate on the event for the time_estimator to use next sync
        est_time, confidence = estimate_release_time(event.isin, engine)
        if est_time and event.expected_time_local is None:
            event.expected_time_local = est_time
            event.time_confidence = confidence

        session.commit()
        # Detach objects so they survive session close
        session.expunge_all()
    finally:
        session.close()

    if not snapshot:
        logger.warning(
            "No expectations snapshot for event %s — running ensemble without it", event.id
        )

    logger.info("Running ensemble for %s %s", company.name, event.fiscal_period)
    result = run_ensemble(event, company, news_item, snapshot, engine)

    decision = TradeDecision(
        id=str(uuid.uuid4()),
        earnings_event_id=event.id,
        decision=result.decision,
        confidence=result.confidence,
        expected_upside_pct=result.expected_upside_pct,
        reasoning_summary=result.reasoning_summary,
        interpreter_a_run_id=result.interpreter_a_run_id,
        interpreter_b_run_id=result.interpreter_b_run_id,
        reaction_run_id=result.reaction_run_id,
        decider_run_id=result.decider_run_id,
        expectations_snapshot_id=snapshot.id if snapshot else None,
        created_at=datetime.now(timezone.utc),
    )
    session2 = get_session(engine)
    try:
        session2.add(decision)
        session2.commit()
    finally:
        session2.close()

    logger.info(
        "Trade decision: %s %s → %s (confidence=%.2f, upside=%.1f%%)",
        company.name, event.fiscal_period,
        result.decision, result.confidence or 0, result.expected_upside_pct or 0,
    )
    return decision


def scan_recent_news(engine, hours: int = 1) -> list[TradeDecision]:
    """
    Scan unmatched news items from the last `hours` hours.
    Called periodically to catch earnings releases as they arrive.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    session = get_session(engine)
    try:
        already_linked = {
            e.news_item_id
            for e in session.query(EarningsEvent.news_item_id).all()
            if e.news_item_id
        }
        recent = session.scalars(
            select(NewsItem).where(NewsItem.fetched_at >= cutoff)
        ).all()
        unmatched = [n for n in recent if n.id not in already_linked]
    finally:
        session.close()

    decisions = []
    for item in unmatched:
        d = handle_news_item(item, engine)
        if d:
            decisions.append(d)
    return decisions
