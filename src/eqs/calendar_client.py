"""
EQS financial calendar client.

NOTE: The exact calendar endpoint is not yet confirmed. Run `discover_routes()`
to list all available /wp-json/eqsnews/v1/ routes, then update CALENDAR_API below.
"""
import logging
from datetime import date

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://www.eqs-news.com"
# Best-guess endpoint — update once confirmed via discover_routes()
CALENDAR_API = f"{BASE_URL}/wp-json/eqsnews/v1/financialcalendar"
TIMEOUT = 15.0


async def fetch_calendar_events(
    client: httpx.AsyncClient,
    isin: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[dict]:
    params: dict = {}
    if isin:
        params["isin"] = isin
    if from_date:
        params["from"] = from_date.isoformat()
    if to_date:
        params["to"] = to_date.isoformat()

    resp = await client.get(CALENDAR_API, params=params, timeout=TIMEOUT)
    if resp.status_code == 404:
        logger.warning(
            "Calendar endpoint %s returned 404. Run discover_routes() to find the correct path.",
            CALENDAR_API,
        )
        return []
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    return data.get("records", data.get("data", []))


async def discover_routes() -> list[str]:
    """Print all EQS routes exposed by the WordPress REST API — useful for finding the calendar endpoint."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/wp-json", timeout=TIMEOUT)
        resp.raise_for_status()
    routes = list(resp.json().get("routes", {}).keys())
    eqs_routes = [r for r in routes if "eqs" in r.lower()]
    logger.info("Available EQS routes:\n%s", "\n".join(eqs_routes))
    return eqs_routes
