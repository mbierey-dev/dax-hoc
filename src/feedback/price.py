"""Fetch closing prices for T-1 and T0, compute announcement-day return."""

import logging
import uuid
import warnings
from datetime import date, datetime, timedelta, timezone

import yfinance as yf

from config import BENCHMARK_TICKER
from db import get_session
from db.models import Company, EarningsEvent, PriceReaction

warnings.filterwarnings("ignore")  # suppress yfinance noise

logger = logging.getLogger(__name__)


def _pick_t_minus_1_t0(df, t0: date) -> tuple[float, float, date] | None:
    """Return (close_t_minus_1, close_t0, date_t_minus_1) or None if unavailable."""
    if df is None or df.empty:
        return None
    df = df.copy()
    df.index = df.index.normalize()
    dates = df.index.date

    pre = df[dates < t0]
    if pre.empty:
        return None
    close_tm1 = float(pre["Close"].iloc[-1])
    date_tm1 = pre.index[-1].date()

    on = df[dates == t0]
    if on.empty:
        return None
    close_t0 = float(on["Close"].iloc[0])

    return close_tm1, close_t0, date_tm1


def _fetch_history(symbol: str, t0: date):
    try:
        return yf.Ticker(symbol).history(
            start=t0 - timedelta(days=7),
            end=t0 + timedelta(days=1),
            auto_adjust=True,
        )
    except Exception as e:
        logger.warning("yfinance error for %s: %s", symbol, e)
        return None


def fetch_and_store(
    event: EarningsEvent,
    company: Company,
    engine,
) -> PriceReaction | None:
    """Fetch T-1 and T0 closing prices via yfinance, persist a PriceReaction row.

    Also fetches MSCI World benchmark (config.BENCHMARK_TICKER) over the same window
    and computes abnormal return = stock return - benchmark return.

    Returns None if stock price data is unavailable for the required dates.
    """
    t0 = event.expected_date
    if t0 is None:
        logger.warning("No expected_date for event %s — skipping price fetch", event.id)
        return None

    used_symbol = None
    picked = None
    for symbol in [s for s in [company.ticker, company.isin] if s]:
        df = _fetch_history(symbol, t0)
        picked = _pick_t_minus_1_t0(df, t0)
        if picked is not None:
            used_symbol = symbol
            break

    if picked is None or used_symbol is None:
        logger.warning(
            "No price data for %s (%s) — skipping", company.name, company.isin
        )
        return None

    close_t_minus_1, close_t0, date_t_minus_1 = picked
    return_t0 = (close_t0 / close_t_minus_1) - 1

    # Benchmark — failure here should not drop the row.
    bench_df = _fetch_history(BENCHMARK_TICKER, t0)
    bench_picked = _pick_t_minus_1_t0(bench_df, t0)
    if bench_picked is None:
        logger.warning(
            "No benchmark (%s) price data for %s on %s", BENCHMARK_TICKER, company.name, t0
        )
        bench_close_tm1 = bench_close_t0 = bench_return = abnormal_return = None
    else:
        bench_close_tm1, bench_close_t0, _ = bench_picked
        bench_return = (bench_close_t0 / bench_close_tm1) - 1
        abnormal_return = return_t0 - bench_return

    price_reaction = PriceReaction(
        id=str(uuid.uuid4()),
        earnings_event_id=event.id,
        ticker=used_symbol,
        date_t_minus_1=date_t_minus_1,
        date_t0=t0,
        close_t_minus_1=close_t_minus_1,
        close_t0=close_t0,
        return_t0=return_t0,
        benchmark_ticker=BENCHMARK_TICKER,
        benchmark_close_t_minus_1=bench_close_tm1,
        benchmark_close_t0=bench_close_t0,
        benchmark_return_t0=bench_return,
        abnormal_return_t0=abnormal_return,
        fetched_at=datetime.now(timezone.utc),
    )

    session = get_session(engine)
    try:
        session.add(price_reaction)
        session.commit()
    except Exception:
        session.rollback()
        logger.warning("PriceReaction already exists for event %s", event.id)
        return None
    finally:
        session.close()

    logger.info(
        "Price reaction for %s %s: T-1=%.2f T0=%.2f return=%.2f%% bench=%s abnormal=%s",
        company.name, event.fiscal_period,
        close_t_minus_1, close_t0, return_t0 * 100,
        f"{bench_return * 100:.2f}%" if bench_return is not None else "n/a",
        f"{abnormal_return * 100:.2f}%" if abnormal_return is not None else "n/a",
    )
    return price_reaction
