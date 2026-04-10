import logging
import re
from dataclasses import dataclass

from db.models import Company, EarningsEvent, ExpectationsSnapshot, NewsItem
from llm.registry import call_llm
from reaction.analyzer import analyze

logger = logging.getLogger(__name__)

_INTERPRETER_PROMPT = """\
You are a financial analyst evaluating an earnings announcement.

Company: {company_name} ({isin}, {index_name} index)
Industry: {industry}
Fiscal period: {fiscal_period}

PRE-RELEASE EXPECTATIONS (what the market expected before this announcement):
{narrative_md}

EARNINGS ANNOUNCEMENT CONTENT:
{news_content}

Analyze the announcement and estimate the likely short-term stock market reaction. Cover:
- Beat / in-line / miss on the key KPIs relevant to this company
- Guidance vs. prior guidance (maintained / raised / cut)
- Key positive and negative surprises
- Overall reaction estimate: strong positive / positive / neutral / negative / strong negative
  with a 1–2 sentence rationale
"""

_DECIDER_PROMPT = """\
You are the final decision-maker in a short-term earnings-driven trading system.

Company: {company_name} ({isin}, {index_name} index)
Fiscal period: {fiscal_period}
Announcement released at: {actual_release_at}

PRE-RELEASE TRADE THESIS (conditions that should be met to buy):
{trade_thesis_md}

ANALYST A — CONTENT INTERPRETATION:
{interpreter_a}

ANALYST B — CONTENT INTERPRETATION:
{interpreter_b}

POST-RELEASE MARKET REACTION ANALYSIS:
{reaction}

Make a final buy/skip decision. Investment thesis:
BUY only if the stock is highly likely to rise at least an additional 5% as a direct result \
of this announcement AND the move is not yet fully priced in.

Respond in exactly this format (nothing before or after):
DECISION: BUY or SKIP
CONFIDENCE: 0.00 to 1.00
EXPECTED_UPSIDE_PCT: e.g. 7.5
REASONING: 2–4 sentence summary.
"""


@dataclass
class EnsembleResult:
    decision: str
    confidence: float | None
    expected_upside_pct: float | None
    reasoning_summary: str
    interpreter_a_run_id: str
    interpreter_b_run_id: str
    reaction_run_id: str
    decider_run_id: str


def run(
    event: EarningsEvent,
    company: Company,
    news_item: NewsItem,
    snapshot: ExpectationsSnapshot | None,
    engine,
) -> EnsembleResult:
    eid = event.id
    narrative = snapshot.narrative_md if snapshot else "(no pre-release narrative available)"
    thesis = snapshot.trade_thesis_md if snapshot else "(no pre-release trade thesis available)"

    # Interpreters A and B work from supplied content only (no web search)
    interp_prompt = _INTERPRETER_PROMPT.format(
        company_name=company.name,
        isin=company.isin,
        index_name=company.index_name,
        industry=company.industry or "N/A",
        fiscal_period=event.fiscal_period,
        narrative_md=narrative,
        news_content=news_item.content or news_item.headline or "(no content available)",
    )
    interp_a, run_a_id = call_llm("interpreter_a", interp_prompt, engine, eid)
    interp_b, run_b_id = call_llm("interpreter_b", interp_prompt, engine, eid)

    # Reaction analyst uses web search for live price data
    reaction_text, run_r_id = analyze(event, company, engine)

    # Decider synthesizes all inputs
    decider_prompt = _DECIDER_PROMPT.format(
        company_name=company.name,
        isin=company.isin,
        index_name=company.index_name,
        fiscal_period=event.fiscal_period,
        actual_release_at=str(event.actual_release_at),
        trade_thesis_md=thesis,
        interpreter_a=interp_a,
        interpreter_b=interp_b,
        reaction=reaction_text,
    )
    decider_text, run_d_id = call_llm("decider", decider_prompt, engine, eid)

    decision, confidence, upside_pct, reasoning = _parse_decision(decider_text)
    logger.info(
        "Ensemble result for %s %s: %s (confidence=%.2f, upside=%.1f%%)",
        company.name, event.fiscal_period, decision, confidence or 0, upside_pct or 0,
    )
    return EnsembleResult(
        decision=decision,
        confidence=confidence,
        expected_upside_pct=upside_pct,
        reasoning_summary=reasoning,
        interpreter_a_run_id=run_a_id,
        interpreter_b_run_id=run_b_id,
        reaction_run_id=run_r_id,
        decider_run_id=run_d_id,
    )


def _parse_decision(text: str) -> tuple[str, float | None, float | None, str]:
    decision = "skip"
    confidence: float | None = None
    upside_pct: float | None = None
    reasoning = text  # fallback: store full text if structured parsing fails

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

    if m := re.search(r"REASONING:\s*(.+)", text, re.I | re.DOTALL):
        reasoning = m.group(1).strip()

    return decision, confidence, upside_pct, reasoning
