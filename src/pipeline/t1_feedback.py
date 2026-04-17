"""T+1 feedback pipeline: fetch price reactions and run feedback LLM for processed events."""

import logging

from sqlalchemy import select

from db import get_session
from db.models import (
    Company,
    EarningsEvent,
    FeedbackReport,
    PriceReaction,
    TradeDecision,
)
from feedback.analyst import analyze
from feedback.price import fetch_and_store

logger = logging.getLogger(__name__)


def run(engine) -> int:
    """
    Find all processed events that don't yet have a FeedbackReport,
    fetch price reactions, and run the feedback analyst LLM.
    Idempotent — events with an existing FeedbackReport are skipped.
    Returns count of feedback reports created.
    """
    session = get_session(engine)
    try:
        # All processed events
        events = session.scalars(
            select(EarningsEvent).where(EarningsEvent.status == "processed")
        ).all()

        if not events:
            logger.info("No processed events found")
            return 0

        event_ids = [e.id for e in events]

        # Trade decisions keyed by earnings_event_id
        decisions = {
            td.earnings_event_id: td
            for td in session.scalars(
                select(TradeDecision).where(
                    TradeDecision.earnings_event_id.in_(event_ids)
                )
            ).all()
        }

        # Already-reported trade_decision_ids
        already_reported = set(
            session.scalars(
                select(FeedbackReport.trade_decision_id).where(
                    FeedbackReport.trade_decision_id.in_(
                        [td.id for td in decisions.values()]
                    )
                )
            ).all()
        )

        # Existing price reactions keyed by earnings_event_id
        existing_prices = {
            pr.earnings_event_id: pr
            for pr in session.scalars(
                select(PriceReaction).where(
                    PriceReaction.earnings_event_id.in_(event_ids)
                )
            ).all()
        }

        companies = {
            c.isin: c
            for c in session.scalars(
                select(Company).where(
                    Company.isin.in_([e.isin for e in events])
                )
            ).all()
        }
    finally:
        session.expunge_all()
        session.close()

    count = 0
    for event in events:
        decision = decisions.get(event.id)
        if not decision:
            logger.warning("No TradeDecision for event %s — skipping", event.id)
            continue

        if decision.id in already_reported:
            logger.debug("FeedbackReport already exists for decision %s — skipping", decision.id)
            continue

        company = companies.get(event.isin)
        if not company:
            logger.warning("No company row for ISIN %s — skipping", event.isin)
            continue

        # Fetch or reuse price reaction
        price_reaction = existing_prices.get(event.id)
        if not price_reaction:
            price_reaction = fetch_and_store(event, company, engine)

        logger.info(
            "Running T+1 feedback for %s %s", company.name, event.fiscal_period
        )
        analyze(event, company, decision, price_reaction, engine)
        count += 1

    logger.info("T+1 feedback complete: %d report(s) created", count)
    return count
