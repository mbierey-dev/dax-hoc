import json
import logging
import uuid
from datetime import datetime, timezone

from db import get_session
from db.models import Company, EarningsEvent, ExpectationsSnapshot
from expectations import pre_ann_prices
from llm.registry import call_llm

logger = logging.getLogger(__name__)

_PROMPT = """\
You are a financial analyst preparing for an upcoming earnings announcement.

Company: {company_name} ({isin}, {index_name} index)
Industry: {industry}
Earnings event: {fiscal_period} ({event_type})
Expected release date: {expected_date}

Your task:
1. Research what analysts and the market currently expect from this earnings release.
2. Identify the key KPIs and events that matter most for THIS company and situation — do not \
default to generic revenue/EPS if something else is more important. \
3. Define (a maximum of 3) key concrete , company-specific conditions under which buying the stock after the \
announcement would be recommended.

Structure your response with exactly these three sections:

## Market Narrative & Key Watchpoints
[What the market expects, consensus on the most relevant KPIs, prior guidance, known \
tailwinds/risks, what is already priced in.]

## Trade Thesis
[Specific, concrete conditions to buy. E.g. "Revenue must beat consensus by >3% AND \
full-year guidance must not be cut" — or whatever actually applies here. Also note \
deal-breakers even if there's a headline beat.]

## Sources
[Comma-separated list of URLs or sources consulted]
"""


def research(event: EarningsEvent, company: Company, engine) -> ExpectationsSnapshot:
    """Run web research at T-1, persist and return an ExpectationsSnapshot."""
    prompt = _PROMPT.format(
        company_name=company.name,
        isin=company.isin,
        index_name=company.index_name,
        industry=company.industry or "N/A",
        fiscal_period=event.fiscal_period,
        event_type=event.event_type,
        expected_date=str(event.expected_date),
    )

    content, run_id = call_llm(
        role="expectations_researcher",
        prompt=prompt,
        engine=engine,
        earnings_event_id=event.id,
        web_search=True,
    )

    narrative_md, trade_thesis_md, sources = _parse_sections(content)
    gathered_at = datetime.now(timezone.utc)

    prices = pre_ann_prices.fetch(company, gathered_at.date())

    snapshot = ExpectationsSnapshot(
        id=str(uuid.uuid4()),
        earnings_event_id=event.id,
        gathered_at=gathered_at,
        narrative_md=narrative_md,
        trade_thesis_md=trade_thesis_md,
        sources_json=json.dumps(sources),
        raw_research_text=content,
        llm_run_id=run_id,
        pre_ann_ticker=prices.ticker if prices else None,
        pre_ann_return_1d=prices.return_1d if prices else None,
        pre_ann_return_3d=prices.return_3d if prices else None,
        pre_ann_return_7d=prices.return_7d if prices else None,
        pre_ann_abnormal_return_1d=prices.abnormal_return_1d if prices else None,
        pre_ann_abnormal_return_3d=prices.abnormal_return_3d if prices else None,
        pre_ann_abnormal_return_7d=prices.abnormal_return_7d if prices else None,
        pre_ann_fetched_at=gathered_at if prices else None,
    )
    session = get_session(engine)
    try:
        session.add(snapshot)
        session.commit()
    finally:
        session.close()

    return snapshot


def _parse_sections(text: str) -> tuple[str, str, list[str]]:
    buckets: dict[str, list[str]] = {"narrative": [], "thesis": [], "sources": []}
    current: str | None = None
    for line in text.splitlines():
        if "## Market Narrative" in line:
            current = "narrative"
        elif "## Trade Thesis" in line:
            current = "thesis"
        elif "## Sources" in line:
            current = "sources"
        elif current:
            buckets[current].append(line)

    narrative = "\n".join(buckets["narrative"]).strip()
    thesis = "\n".join(buckets["thesis"]).strip()
    raw_sources = "\n".join(buckets["sources"]).strip()
    sources = (
        [s.strip() for s in raw_sources.replace("\n", ",").split(",") if s.strip()]
        if raw_sources
        else []
    )
    return narrative, thesis, sources
