import re
from datetime import datetime, timezone

from db.models import Company, EarningsEvent
from llm.registry import call_llm

_PROMPT = """\
You are a financial analyst. {company_name} ({isin}, {index_name} index) has just released \
earnings for {fiscal_period} ({event_type}).

Search for the official earnings announcement or press release and summarize it. \
Start your response with exactly this line (ISO 8601 UTC timestamp, or the literal word "unknown"):
RELEASE_DATETIME: <timestamp or unknown>

Then provide the summary of the eaernings announcements.
Focus on the most important parts (that were directly released in or with the earnings announcement) that could have an impact on the stock market reaction to the earnings announcement.
Use exactly these three sections:

## Reported KPIs
[All major reported figures — revenue, operating profit, EBIT, net income, EPS, or the \
company-specific KPIs that analysts and the market are watching out for in this release.
Include actuals and prior-year (yoy) comparisons where available.]

## Guidance
[Any changes to full-year or next-period guidance: raised / maintained / cut. Quote specific \
figures where available. State "No guidance update mentioned" if absent.]

## Key Qualitative Highlights
[Only include information that is materially relevant for near-term stock price development: \
significant management commentary on strategy or outlook, unexpected business developments, \
major macro or sector factors explicitly highlighted in the release. Omit boilerplate and \
standard legal language.]
"""


def run(event: EarningsEvent, company: Company, engine) -> tuple[str, str, datetime | None]:
    """Fetch and summarize the earnings announcement via web search.
    Returns (summary, run_id, actual_release_at)."""
    prompt = _PROMPT.format(
        company_name=company.name,
        isin=company.isin,
        index_name=company.index_name,
        fiscal_period=event.fiscal_period,
        event_type=event.event_type,
    )
    raw_text, run_id = call_llm(
        role="announcement_fetcher",
        prompt=prompt,
        engine=engine,
        earnings_event_id=event.id,
        web_search=True,
    )
    release_at, summary = _parse_response(raw_text)
    return summary, run_id, release_at


def _parse_response(text: str) -> tuple[datetime | None, str]:
    release_at: datetime | None = None
    summary = text

    m = re.match(r"RELEASE_DATETIME:\s*(\S+)\s*\n?", text)
    if m:
        value = m.group(1).strip()
        if value.lower() != "unknown":
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                release_at = dt.astimezone(timezone.utc).replace(tzinfo=None)
            except ValueError:
                pass
        summary = text[m.end():].strip()

    return release_at, summary
