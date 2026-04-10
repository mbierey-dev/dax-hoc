import logging
import re

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.eqs-news.com"
NEWS_API = f"{BASE_URL}/wp-json/eqsnews/v1/news"
DETAIL_API = f"{BASE_URL}/wp-json/eqsnews/v1/newsdetail"

TIMEOUT = 15.0


async def fetch_latest_news(
    client: httpx.AsyncClient, page_limit: int = 20
) -> list[dict]:
    resp = await client.get(NEWS_API, params={"pageLimit": page_limit}, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    return data.get("records", data.get("data", []))


async def fetch_news_detail(client: httpx.AsyncClient, news_id: str) -> dict | None:
    # Strip language suffix if present (e.g. "abc123_en" -> "abc123")
    clean_id = re.sub(r"_[a-z]{2}$", "", news_id)
    resp = await client.get(
        DETAIL_API, params={"news_id": clean_id}, timeout=TIMEOUT
    )
    if resp.status_code != 200:
        logger.warning("Detail API returned %d for %s", resp.status_code, news_id)
        return None
    data = resp.json()
    return data.get("records", data)


async def fetch_news_content(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url, timeout=TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("Failed to fetch content from %s: %s", url, e)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    article = soup.find("article") or soup.find("main") or soup.find(
        "div", class_=re.compile(r"news.*content|article|entry", re.I)
    )

    if article:
        text = article.get_text(separator="\n", strip=True)
    else:
        body = soup.find("body")
        text = body.get_text(separator="\n", strip=True) if body else ""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)
