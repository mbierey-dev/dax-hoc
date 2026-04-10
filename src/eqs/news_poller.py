import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from db import bootstrap, get_engine, get_session
from db.models import NewsItem
from eqs import client as eqs_client

logger = logging.getLogger(__name__)


def _parse_datetime(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S+00:00"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


async def _enrich_item(
    client: httpx.AsyncClient, item: dict
) -> tuple[str | None, str | None]:
    news_id = item.get("id", "")
    detail = await eqs_client.fetch_news_detail(client, news_id)
    share_url = None
    content = None
    if detail and isinstance(detail, dict):
        share_url = detail.get("share_url")
        if share_url:
            content = await eqs_client.fetch_news_content(client, share_url)
    return share_url, content


async def poll_once(engine) -> int:
    """Fetch latest EQS news, deduplicate, enrich with content, store. Returns new-item count."""
    async with httpx.AsyncClient() as client:
        items = await eqs_client.fetch_latest_news(client)

    if not items:
        return 0

    session = get_session(engine)
    try:
        existing_ids = set(
            session.scalars(
                select(NewsItem.id).where(
                    NewsItem.id.in_([item.get("id", "") for item in items])
                )
            ).all()
        )
        new_items = [i for i in items if i.get("id", "") not in existing_ids]
        if not new_items:
            return 0
    finally:
        session.close()

    logger.info("Found %d new items, enriching...", len(new_items))

    async with httpx.AsyncClient() as client:
        enrichments = await asyncio.gather(
            *[_enrich_item(client, item) for item in new_items],
            return_exceptions=True,
        )

    session = get_session(engine)
    try:
        for item, enrichment in zip(new_items, enrichments):
            if isinstance(enrichment, Exception):
                logger.warning("Failed to enrich %s: %s", item.get("id"), enrichment)
                share_url, content = None, None
            else:
                share_url, content = enrichment

            locale_val = item.get("locale", "")
            if isinstance(locale_val, list):
                locale_val = ",".join(locale_val)

            session.add(
                NewsItem(
                    id=item.get("id", ""),
                    created_at=_parse_datetime(item.get("dtcreated")),
                    created_at_utc=_parse_datetime(item.get("dateUtc")),
                    category=item.get("category"),
                    category_code=item.get("categoryCode"),
                    company_name=item.get("companyName"),
                    company_uuid=item.get("companyUUID"),
                    isin=item.get("isin"),
                    headline=item.get("headline"),
                    language=item.get("language"),
                    locale=locale_val,
                    timezone=item.get("timezone"),
                    content=content,
                    share_url=share_url,
                    fetched_at=datetime.now(timezone.utc),
                    raw_json=json.dumps(item, ensure_ascii=False),
                )
            )
        session.commit()
        return len(new_items)
    finally:
        session.close()


async def poll_loop(interval_seconds: int = 30, engine=None) -> None:
    engine = engine or get_engine()
    bootstrap(engine)
    logger.info("Starting EQS news poll loop (interval=%ds)", interval_seconds)
    while True:
        try:
            count = await poll_once(engine)
            if count > 0:
                logger.info("Stored %d new items", count)
            else:
                logger.debug("No new items")
        except Exception:
            logger.exception("Error during poll cycle")
        await asyncio.sleep(interval_seconds)
