import logging
from datetime import date, timedelta

from sqlalchemy import and_, select

from db import get_session
from db.models import Company, EarningsEvent, ExpectationsSnapshot
from expectations.researcher import research

logger = logging.getLogger(__name__)


def run(engine) -> int:
    """
    T-1 preparation job: find events scheduled for tomorrow that don't yet have an
    expectations snapshot, then run the researcher for each.
    Returns count of events prepared.
    """
    tomorrow = date.today() + timedelta(days=1)

    session = get_session(engine)
    try:
        already_researched = {
            row.earnings_event_id
            for row in session.query(ExpectationsSnapshot.earnings_event_id).all()
        }
        events = session.scalars(
            select(EarningsEvent).where(
                and_(
                    EarningsEvent.expected_date == tomorrow,
                    EarningsEvent.status == "scheduled",
                )
            )
        ).all()
        todo = [e for e in events if e.id not in already_researched]

        companies = {
            c.isin: c
            for c in session.query(Company)
            .filter(Company.isin.in_([e.isin for e in todo]))
            .all()
        }
    finally:
        session.close()

    prepared = 0
    for event in todo:
        company = companies.get(event.isin)
        if not company:
            logger.warning("No company row for ISIN %s — skipping", event.isin)
            continue
        logger.info("Researching %s %s", company.name, event.fiscal_period)
        research(event, company, engine)
        prepared += 1

    logger.info("Daily prep complete: %d event(s) prepared", prepared)
    return prepared
