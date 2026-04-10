import logging
from datetime import timedelta

from sqlalchemy import and_, select

from db import get_session
from db.models import EarningsEvent, NewsItem

logger = logging.getLogger(__name__)

# Headline/category keywords that suggest an earnings announcement
_EARNINGS_KEYWORDS = (
    "quartal", "quarterly", "halbjahr", "half-year", "half year",
    "jahresabschluss", "annual results", "jahresergebnis",
    "vorläufige ergebnisse", "preliminary results",
    "ergebnis", "umsatz", "geschäftsbericht", "quartalsbericht",
    "q1", "q2", "q3", "q4", "h1", "h2",
)

# How many days either side of expected_date we accept as a match
_WINDOW_DAYS = 2


def is_earnings_news(item: NewsItem) -> bool:
    headline = (item.headline or "").lower()
    category = (item.category or "").lower()
    cat_code = (item.category_code or "").lower()
    return any(k in t for k in _EARNINGS_KEYWORDS for t in (headline, category, cat_code))


def find_matching_event(item: NewsItem, engine) -> EarningsEvent | None:
    """Match a news item to a scheduled EarningsEvent by ISIN + date proximity."""
    if not item.isin or not is_earnings_news(item):
        return None

    release_dt = item.created_at_utc or item.created_at
    if not release_dt:
        return None

    release_date = release_dt.date()
    window_start = release_date - timedelta(days=_WINDOW_DAYS)
    window_end = release_date + timedelta(days=_WINDOW_DAYS)

    session = get_session(engine)
    try:
        return session.scalars(
            select(EarningsEvent).where(
                and_(
                    EarningsEvent.isin == item.isin,
                    EarningsEvent.status == "scheduled",
                    EarningsEvent.expected_date >= window_start,
                    EarningsEvent.expected_date <= window_end,
                )
            )
        ).first()
    finally:
        session.close()
