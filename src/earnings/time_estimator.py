import logging
from datetime import time
from statistics import mean

from sqlalchemy import select

from db import get_session
from db.models import EarningsEvent

logger = logging.getLogger(__name__)


def estimate_release_time(isin: str, engine) -> tuple[time | None, str]:
    """
    Look at prior actual_release_at times for this ISIN and return an
    (estimated_time_of_day, confidence) pair for the next event.

    confidence values: "exact" (≥3 consistent events), "estimated" (≥2), "unknown"
    """
    session = get_session(engine)
    try:
        past = session.scalars(
            select(EarningsEvent).where(
                EarningsEvent.isin == isin,
                EarningsEvent.actual_release_at.is_not(None),
            )
        ).all()
    finally:
        session.close()

    if not past:
        return None, "unknown"

    minutes = [e.actual_release_at.hour * 60 + e.actual_release_at.minute for e in past]
    avg = int(mean(minutes))
    est = time(avg // 60, avg % 60)

    # If all past releases are within 30 min of the average, call it "exact"
    if len(past) >= 3 and all(abs(m - avg) <= 30 for m in minutes):
        confidence = "exact"
    elif len(past) >= 2:
        confidence = "estimated"
    else:
        confidence = "unknown"

    logger.debug("%s: estimated release time %s (n=%d, confidence=%s)", isin, est, len(past), confidence)
    return est, confidence
