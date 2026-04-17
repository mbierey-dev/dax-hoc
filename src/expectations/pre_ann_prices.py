"""Fetch pre-announcement abnormal returns for the 1d/3d/7d windows before T-1."""

import logging
import warnings
from dataclasses import dataclass
from datetime import date, timedelta

import yfinance as yf

from config import BENCHMARK_TICKER
from db.models import Company

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


@dataclass
class PreAnnReturns:
    ticker: str
    return_1d: float | None
    return_3d: float | None
    return_7d: float | None
    abnormal_return_1d: float | None
    abnormal_return_3d: float | None
    abnormal_return_7d: float | None


def fetch(company: Company, t1_date: date) -> PreAnnReturns | None:
    """Compute abnormal returns vs MSCI World for 1d/3d/7d windows ending at T-1 close.

    Returns None if price data for the stock is unavailable.
    """
    closes = _get_closes(company, t1_date)
    if closes is None:
        return None
    ticker, stock_closes = closes

    bench_closes = _fetch_closes(BENCHMARK_TICKER, t1_date)

    def _window_return(series: list[float], n: int) -> float | None:
        if len(series) < n + 1:
            return None
        return series[-1] / series[-(n + 1)] - 1

    r1 = _window_return(stock_closes, 1)
    r3 = _window_return(stock_closes, 3)
    r7 = _window_return(stock_closes, 7)

    b1 = _window_return(bench_closes, 1) if bench_closes else None
    b3 = _window_return(bench_closes, 3) if bench_closes else None
    b7 = _window_return(bench_closes, 7) if bench_closes else None

    def _abnormal(stock: float | None, bench: float | None) -> float | None:
        return stock - bench if stock is not None and bench is not None else None

    return PreAnnReturns(
        ticker=ticker,
        return_1d=r1,
        return_3d=r3,
        return_7d=r7,
        abnormal_return_1d=_abnormal(r1, b1),
        abnormal_return_3d=_abnormal(r3, b3),
        abnormal_return_7d=_abnormal(r7, b7),
    )


def _get_closes(company: Company, t1_date: date) -> tuple[str, list[float]] | None:
    for symbol in [s for s in [company.ticker, company.isin] if s]:
        closes = _fetch_closes(symbol, t1_date)
        if closes:
            return symbol, closes
    logger.warning("No pre-ann price data for %s (%s)", company.name, company.isin)
    return None


def _fetch_closes(symbol: str, t1_date: date) -> list[float] | None:
    """Return sorted list of closing prices for the 20 calendar days ending at t1_date."""
    try:
        df = yf.Ticker(symbol).history(
            start=t1_date - timedelta(days=20),
            end=t1_date + timedelta(days=1),
            auto_adjust=True,
        )
    except Exception as e:
        logger.warning("yfinance error for %s: %s", symbol, e)
        return None

    if df is None or df.empty:
        return None

    df = df.copy()
    df.index = df.index.normalize()
    df = df[df.index.date <= t1_date]
    if df.empty:
        return None

    return [float(v) for v in df["Close"].tolist()]
