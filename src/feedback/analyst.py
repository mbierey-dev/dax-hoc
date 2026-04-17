"""T+1 feedback analyst: evaluate trade decisions against actual outcomes."""

import logging
import re
import uuid
from datetime import datetime, timezone

from db import get_session
from db.models import (
    Company,
    EarningsEvent,
    ExpectationsSnapshot,
    FeedbackReport,
    LLMRun,
    PriceReaction,
    TradeDecision,
)
from llm.registry import call_llm

logger = logging.getLogger(__name__)

_PROMPT = """\
You are a trading system performance analyst conducting a post-mortem review.

Company: {company_name} ({isin}, {index_name} index)
Industry: {industry}
Fiscal period: {fiscal_period} ({event_type})
Announcement date: {event_date}

--- PRE-RELEASE EXPECTATIONS (T-1) ---
Market narrative:
{narrative_md}

Trade thesis (conditions to buy):
{trade_thesis_md}

--- EARNINGS ANNOUNCEMENT SUMMARY (T0) ---
{announcement_summary}

--- ANALYST INTERPRETATIONS ---
Analyst A:
{interpreter_a_response}

Analyst B:
{interpreter_b_response}

--- SYSTEM DECISION ---
Decision: {decision} | Confidence: {confidence} | Expected upside: {expected_upside_pct}%
Reasoning: {reasoning_summary}
{missing_information_line}

--- ACTUAL OUTCOME ---
Stock return on announcement day ({event_date}): {return_pct}%
(T-1 close: {close_t_minus_1}, T0 close: {close_t0})

Using web search, look up what the actual market and news narrative was around {company_name}'s \
{fiscal_period} announcement on {event_date}. Then evaluate the system's decision.

Structure your response with exactly these three sections:

## Decision Assessment
Was the decision correct given what was knowable at T0?
Classify as: CORRECT / INCORRECT / PARTIAL.
The actual return was {return_pct}% — a BUY decision is correct if return > +3%, \
SKIP is correct if return < +3%.
Explain your reasoning in 3-5 sentences. Include what the market narrative actually was.

## Key Learnings
What signals were present in the announcement or expectations that the system \
over/underweighted? What specific patterns or red flags should be weighted differently \
for similar companies or situations? Be concrete — name the specific KPIs, guidance \
changes, or qualitative factors that mattered most.

## Improvement Suggestions
List 3-5 specific, actionable changes to the research or decision process for future \
announcements. \
Format as a bullet list.

In terms of learnings and suggested improvements -- don't focus on this specific company/industry, 
but rather come of with general learnings / suggestions that could help our earnings 
announcement trading system in the future. 

"""


def analyze(
    event: EarningsEvent,
    company: Company,
    trade_decision: TradeDecision,
    price_reaction: PriceReaction | None,
    engine,
) -> FeedbackReport:
    """Run the feedback analyst LLM and persist a FeedbackReport."""

    # Fetch LLM run responses and snapshot
    session = get_session(engine)
    try:
        announcement_text = _get_run_response(session, trade_decision.announcement_run_id)
        interp_a_text = _get_run_response(session, trade_decision.interpreter_a_run_id)
        interp_b_text = _get_run_response(session, trade_decision.interpreter_b_run_id)

        snapshot = None
        if trade_decision.expectations_snapshot_id:
            snapshot = session.get(ExpectationsSnapshot, trade_decision.expectations_snapshot_id)
    finally:
        session.close()

    narrative_md = snapshot.narrative_md if snapshot else "(not available)"
    thesis_md = snapshot.trade_thesis_md if snapshot else "(not available)"

    missing_line = ""
    if trade_decision.missing_information:
        missing_line = f"Missing information flagged: {trade_decision.missing_information}"

    if price_reaction and price_reaction.return_t0 is not None:
        return_pct = f"{price_reaction.return_t0 * 100:.2f}"
        close_t_minus_1 = f"{price_reaction.close_t_minus_1:.2f}"
        close_t0 = f"{price_reaction.close_t0:.2f}"
    else:
        return_pct = "N/A"
        close_t_minus_1 = "N/A"
        close_t0 = "N/A"

    prompt = _PROMPT.format(
        company_name=company.name,
        isin=company.isin,
        index_name=company.index_name,
        industry=company.industry or "N/A",
        fiscal_period=event.fiscal_period,
        event_type=event.event_type or "earnings",
        event_date=str(event.expected_date),
        narrative_md=narrative_md,
        trade_thesis_md=thesis_md,
        announcement_summary=announcement_text,
        interpreter_a_response=interp_a_text,
        interpreter_b_response=interp_b_text,
        decision=trade_decision.decision,
        confidence=f"{trade_decision.confidence:.2f}" if trade_decision.confidence else "N/A",
        expected_upside_pct=f"{trade_decision.expected_upside_pct:.1f}" if trade_decision.expected_upside_pct else "N/A",
        reasoning_summary=trade_decision.reasoning_summary or "",
        missing_information_line=missing_line,
        return_pct=return_pct,
        close_t_minus_1=close_t_minus_1,
        close_t0=close_t0,
    )

    raw_text, run_id = call_llm(
        role="feedback_analyst",
        prompt=prompt,
        engine=engine,
        earnings_event_id=event.id,
        web_search=True,
    )

    decision_correct, market_narrative, key_learnings, improvement_suggestions = _parse(raw_text)

    report = FeedbackReport(
        id=str(uuid.uuid4()),
        earnings_event_id=event.id,
        trade_decision_id=trade_decision.id,
        price_reaction_id=price_reaction.id if price_reaction else None,
        decision_correct=decision_correct,
        key_learnings_md=key_learnings,
        improvement_suggestions_md=improvement_suggestions,
        market_narrative_md=market_narrative,
        raw_feedback_text=raw_text,
        llm_run_id=run_id,
        created_at=datetime.now(timezone.utc),
    )

    session2 = get_session(engine)
    try:
        session2.add(report)
        session2.commit()
    finally:
        session2.close()

    logger.info(
        "Feedback for %s %s: %s", company.name, event.fiscal_period, decision_correct
    )
    return report


def _get_run_response(session, run_id: str | None) -> str:
    if not run_id:
        return "(not available)"
    run = session.get(LLMRun, run_id)
    if not run or not run.response:
        return "(not available)"
    return run.response


def _parse(text: str) -> tuple[str | None, str | None, str | None, str | None]:
    """Parse the three sections and extract the correctness label."""
    decision_correct = None
    if m := re.search(r"\b(CORRECT|INCORRECT|PARTIAL)\b", text):
        decision_correct = m.group(1).lower()

    sections = {"assessment": None, "learnings": None, "suggestions": None}
    current = None
    lines: dict[str, list[str]] = {k: [] for k in sections}

    for line in text.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("## decision assessment"):
            current = "assessment"
            continue
        elif stripped.startswith("## key learnings"):
            current = "learnings"
            continue
        elif stripped.startswith("## improvement suggestions"):
            current = "suggestions"
            continue
        if current:
            lines[current].append(line)

    for key in sections:
        content = "\n".join(lines[key]).strip()
        if content:
            sections[key] = content

    return decision_correct, sections["assessment"], sections["learnings"], sections["suggestions"]
