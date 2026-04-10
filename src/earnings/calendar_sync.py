"""
Sync upcoming earnings events for the tradeable universe.

Source: Yahoo Finance (ISIN → next earnings date)
Scope:  Next 30 days, confirmed dates only (single date, not an estimate range)
"""
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.dialects.sqlite import insert

from db import get_session
from db.models import Company, EarningsEvent
from earnings.yf_calendar import _fiscal_period, fetch

logger = logging.getLogger(__name__)

LOOKAHEAD_DAYS = 30


def sync_all(engine) -> list[EarningsEvent]:
    """
    Fetch next earnings dates for all companies via yfinance.
    Store events scheduled within the next LOOKAHEAD_DAYS days (confirmed only).
    Returns the list of EarningsEvent rows upserted.
    """
    today = date.today()
    cutoff = today + timedelta(days=LOOKAHEAD_DAYS)

    session = get_session(engine)
    try:
        companies = session.query(Company).all()
    finally:
        session.close()

    now = datetime.now(timezone.utc)
    records = []

    for company in companies:
        result = fetch(company.isin)
        if result is None:
            continue
        if not (today <= result.announcement_date <= cutoff):
            continue  # outside next-week window

        fiscal_period = _fiscal_period(result.announcement_date)
        records.append(
            {
                "id": str(uuid.uuid4()),
                "isin": company.isin,
                "fiscal_period": fiscal_period,
                "event_type": "quarterly",  # refined later as we build history
                "expected_date": result.announcement_date,
                "expected_time_local": None,
                "time_confidence": "exact",
                "source": "yahoo_finance",
                "status": "scheduled",
                "actual_release_at": None,
                "news_item_id": None,
                "last_synced_at": now,
            }
        )
        logger.info(
            "  %s (%s): earnings on %s [%s]",
            company.name, company.isin, result.announcement_date, fiscal_period,
        )

    if not records:
        logger.info("No confirmed earnings events in the next %d days.", LOOKAHEAD_DAYS)
        return []

    session = get_session(engine)
    try:
        stmt = insert(EarningsEvent).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["isin", "fiscal_period"],
            set_={
                "expected_date": stmt.excluded.expected_date,
                "time_confidence": stmt.excluded.time_confidence,
                "source": stmt.excluded.source,
                "last_synced_at": stmt.excluded.last_synced_at,
            },
        )
        session.execute(stmt)
        session.commit()
    finally:
        session.close()

    logger.info(
        "Calendar sync done: %d confirmed earnings events in the next %d days.",
        len(records), LOOKAHEAD_DAYS,
    )
    return records
