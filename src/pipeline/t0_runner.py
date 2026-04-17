import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import and_, select

from db import get_session
from db.models import Company, EarningsEvent, ExpectationsSnapshot, TradeDecision
from ensemble.pipeline import run as run_ensemble

logger = logging.getLogger(__name__)


def run(engine) -> list[TradeDecision]:
    """
    T0 pipeline: find today's scheduled events and run the full ensemble for each.
    Idempotent — already-processed events (status='processed') are skipped.
    Returns the list of TradeDecisions created this run.
    """
    today = date.today()

    session = get_session(engine)
    try:
        events = session.scalars(
            select(EarningsEvent).where(
                and_(
                    EarningsEvent.expected_date == today,
                    EarningsEvent.status == "scheduled",
                )
            )
        ).all()

        companies = {
            c.isin: c
            for c in session.query(Company)
            .filter(Company.isin.in_([e.isin for e in events]))
            .all()
        }

        snapshots = {
            row.earnings_event_id: row
            for row in session.scalars(
                select(ExpectationsSnapshot).where(
                    ExpectationsSnapshot.earnings_event_id.in_([e.id for e in events])
                )
            ).all()
        }
    finally:
        session.close()

    decisions = []
    for event in events:
        company = companies.get(event.isin)
        if not company:
            logger.warning("No company row for ISIN %s — skipping", event.isin)
            continue

        snapshot = snapshots.get(event.id)
        if not snapshot:
            logger.warning(
                "No expectations snapshot for %s %s — running ensemble without it",
                company.name, event.fiscal_period,
            )

        logger.info("Running T0 pipeline for %s %s", company.name, event.fiscal_period)
        result = run_ensemble(event, company, snapshot, engine)

        decision = TradeDecision(
            id=str(uuid.uuid4()),
            earnings_event_id=event.id,
            decision=result.decision,
            confidence=result.confidence,
            expected_upside_pct=result.expected_upside_pct,
            reasoning_summary=result.reasoning_summary,
            missing_information=result.missing_information,
            announcement_run_id=result.announcement_run_id,
            interpreter_a_run_id=result.interpreter_a_run_id,
            interpreter_b_run_id=result.interpreter_b_run_id,
            decider_run_id=result.decider_run_id,
            expectations_snapshot_id=snapshot.id if snapshot else None,
            created_at=datetime.now(timezone.utc),
        )

        session2 = get_session(engine)
        try:
            # Mark event processed
            ev = session2.get(EarningsEvent, event.id)
            ev.status = "processed"
            ev.processed_at = datetime.now(timezone.utc)
            session2.add(decision)
            session2.commit()
        finally:
            session2.close()

        logger.info(
            "Decision for %s %s: %s (confidence=%.2f, upside=%.1f%%)",
            company.name, event.fiscal_period,
            result.decision, result.confidence or 0, result.expected_upside_pct or 0,
        )
        decisions.append(decision)

    logger.info("T0 pipeline complete: %d decision(s) made", len(decisions))
    return decisions
