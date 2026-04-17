from db.models import Company, EarningsEvent, ExpectationsSnapshot
from llm.registry import call_llm

_PROMPT = """\
You are a financial analyst evaluating an earnings announcement with respect to the expected
stock market reaction.

Company: {company_name} ({isin}, {index_name} index)
Industry: {industry}
Fiscal period: {fiscal_period}

PRE-RELEASE EXPECTATIONS (what the market expected before this announcement):
{narrative_md}

EARNINGS ANNOUNCEMENT SUMMARY:
{announcement_summary}

Analyze the announcement and estimate the likely short-term stock market reaction. 
If you need any additional (highly relevant) information then please fetch them on your own and include it in the decision.

Cover:
- Beat / in-line / miss on the key KPIs relevant to this company
- Guidance vs. prior guidance (maintained / raised / cut)
- Guidance vs. street consensus 
- Key positive and negative surprises
- Overall reaction estimate: strong positive / positive / neutral / negative / strong negative
  with a 1–2 sentence rationale
"""


def run(
    role: str,
    event: EarningsEvent,
    company: Company,
    announcement_summary: str,
    snapshot: ExpectationsSnapshot | None,
    engine,
) -> tuple[str, str]:
    """Run an interpreter role (interpreter_a or interpreter_b). Returns (response_text, run_id)."""
    narrative = snapshot.narrative_md if snapshot else "(no pre-release narrative available)"
    prompt = _PROMPT.format(
        company_name=company.name,
        isin=company.isin,
        index_name=company.index_name,
        industry=company.industry or "N/A",
        fiscal_period=event.fiscal_period,
        narrative_md=narrative,
        announcement_summary=announcement_summary,
    )
    return call_llm(role=role, prompt=prompt, engine=engine, earnings_event_id=event.id)
