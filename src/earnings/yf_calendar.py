"""
Fetch next earnings announcement date from Yahoo Finance using ISIN directly.

Yahoo Finance returns Earnings Date as:
  - [single date]     → confirmed date
  - [date1, date2]    → unconfirmed window (estimate); we skip these
  - None / missing    → no data

We only store confirmed (single-date) entries.
"""
import logging
import warnings
from dataclasses import dataclass
from datetime import date

import yfinance as yf

warnings.filterwarnings("ignore")  # suppress yfinance noise

logger = logging.getLogger(__name__)


@dataclass
class EarningsDate:
    isin: str
    announcement_date: date
    confirmed: bool  # True = single date; False = range estimate


def fetch(isin: str) -> EarningsDate | None:
    """Return the next confirmed earnings date for an ISIN, or None."""
    try:
        cal = yf.Ticker(isin).calendar
    except Exception as e:
        logger.warning("yfinance error for %s: %s", isin, e)
        return None

    if not cal or "Earnings Date" not in cal:
        return None

    dates = cal["Earnings Date"]
    if not dates:
        return None

    if len(dates) == 1:
        return EarningsDate(isin=isin, announcement_date=dates[0], confirmed=True)

    # Two dates = unconfirmed estimate window — skip
    logger.debug("%s: skipping unconfirmed range %s–%s", isin, dates[0], dates[1])
    return None


def _fiscal_period(announcement_date: date) -> str:
    """
    Derive the reported fiscal period from the announcement date.
    Heuristic: the period that ended in the quarter before the release quarter.

      Release month  →  Reported period
      Jan – Mar      →  Full Year (prior year)
      Apr – Jun      →  Q1 (same year)
      Jul – Sep      →  H1 / Q2 (same year)
      Oct – Dec      →  Q3 (same year)
    """
    m = announcement_date.month
    y = announcement_date.year
    if m <= 3:
        return f"{y - 1}-FY"
    elif m <= 6:
        return f"{y}-Q1"
    elif m <= 9:
        return f"{y}-H1"
    else:
        return f"{y}-Q3"
