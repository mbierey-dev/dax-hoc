import re

from db.models import Company, EarningsEvent
from llm.registry import call_llm

_PROMPT = """\
You are the final decision-maker in a short-term earnings-driven trading system.

Company: {company_name} ({isin}, {index_name} index)
Fiscal period: {fiscal_period}
Announcement released at: {actual_release_at}
{pre_ann_section}
PRE-RELEASE TRADE THESIS (conditions that should be met to buy):
{trade_thesis_md}

ANALYST A — CONTENT INTERPRETATION:
{interpreter_a}

ANALYST B — CONTENT INTERPRETATION:
{interpreter_b}

EARNINGS ANNOUNCEMENT SUMMARY:
{reaction}

Make a final buy/skip decision. Investment thesis:
BUY only if the stock is highly likely to rise at least an additional 5% as a direct result \
of this announcement AND the move is not yet fully priced in.
If you need any additional information then please fetch them on your own and include them in your decision.

Respond in exactly this format (nothing before or after):
DECISION: BUY or SKIP
CONFIDENCE: 0.00 to 1.00
EXPECTED_UPSIDE_PCT: e.g. 7.5
REASONING: 2–4 sentence summary.
MISSING_INFORMATION: (optional) Comma-separated list of specific data points that were absent and would have materially changed the decision. Omit this line entirely if nothing important was missing.
"""


def run(
    event: EarningsEvent,
    company: Company,
    trade_thesis_md: str,
    interpreter_a: str,
    interpreter_b: str,
    reaction: str,
    engine,
    pre_ann_context: str | None = None,
) -> tuple[str, str, str, float | None, float | None, str, str | None]:
    """Run the decider LLM. Returns (raw_text, run_id, decision, confidence, upside_pct, reasoning, missing_information)."""
    if pre_ann_context:
        pre_ann_section = f"PRE-ANNOUNCEMENT PRICE MOMENTUM (vs MSCI World, as of T-1 close):\n{pre_ann_context}\n"
    else:
        pre_ann_section = ""
    prompt = _PROMPT.format(
        company_name=company.name,
        isin=company.isin,
        index_name=company.index_name,
        fiscal_period=event.fiscal_period,
        actual_release_at=str(event.actual_release_at) if event.actual_release_at else "unknown",
        pre_ann_section=pre_ann_section,
        trade_thesis_md=trade_thesis_md,
        interpreter_a=interpreter_a,
        interpreter_b=interpreter_b,
        reaction=reaction,
    )
    raw_text, run_id = call_llm(role="decider", prompt=prompt, engine=engine, earnings_event_id=event.id)
    decision, confidence, upside_pct, reasoning, missing_information = _parse(raw_text)
    return raw_text, run_id, decision, confidence, upside_pct, reasoning, missing_information


def _parse(text: str) -> tuple[str, float | None, float | None, str, str | None]:
    decision = "skip"
    confidence: float | None = None
    upside_pct: float | None = None
    reasoning = text  # fallback if structured parsing fails
    missing_information: str | None = None

    if m := re.search(r"DECISION:\s*(BUY|SKIP)", text, re.I):
        decision = m.group(1).lower()

    if m := re.search(r"CONFIDENCE:\s*([0-9.]+)", text, re.I):
        try:
            confidence = float(m.group(1))
        except ValueError:
            pass

    if m := re.search(r"EXPECTED_UPSIDE_PCT:\s*([0-9.+-]+)", text, re.I):
        try:
            upside_pct = float(m.group(1))
        except ValueError:
            pass

    if m := re.search(r"REASONING:\s*(.+?)(?=\nMISSING_INFORMATION:|\Z)", text, re.I | re.DOTALL):
        reasoning = m.group(1).strip()

    if m := re.search(r"MISSING_INFORMATION:\s*(.+)", text, re.I | re.DOTALL):
        missing_information = m.group(1).strip() or None

    return decision, confidence, upside_pct, reasoning, missing_information
