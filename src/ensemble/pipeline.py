import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from db.models import Company, EarningsEvent, ExpectationsSnapshot
from ensemble import announcement, decider, interpreter

logger = logging.getLogger(__name__)


@dataclass
class EnsembleResult:
    decision: str
    confidence: float | None
    expected_upside_pct: float | None
    reasoning_summary: str
    missing_information: str | None
    announcement_run_id: str
    interpreter_a_run_id: str
    interpreter_b_run_id: str
    decider_run_id: str


def _format_pre_ann(snapshot: ExpectationsSnapshot) -> str | None:
    ar1 = snapshot.pre_ann_abnormal_return_1d
    ar3 = snapshot.pre_ann_abnormal_return_3d
    ar7 = snapshot.pre_ann_abnormal_return_7d
    if ar1 is None and ar3 is None and ar7 is None:
        return None

    def _fmt(v: float | None) -> str:
        return f"{v * 100:+.1f}%" if v is not None else "n/a"

    return (
        f"1d abnormal return: {_fmt(ar1)}\n"
        f"3d abnormal return: {_fmt(ar3)}\n"
        f"7d abnormal return: {_fmt(ar7)}"
    )


def run(
    event: EarningsEvent,
    company: Company,
    snapshot: ExpectationsSnapshot | None,
    engine,
) -> EnsembleResult:
    thesis = snapshot.trade_thesis_md if snapshot else "(no pre-release trade thesis available)"
    pre_ann_context = _format_pre_ann(snapshot) if snapshot else None

    announcement_text, run_ann_id, release_at = announcement.run(event, company, engine)
    if release_at is not None and event.actual_release_at is None:
        event.actual_release_at = release_at
        with Session(engine) as session:
            merged = session.merge(event)
            merged.actual_release_at = release_at
            session.commit()

    interp_a, run_a_id = interpreter.run("interpreter_a", event, company, announcement_text, snapshot, engine)
    interp_b, run_b_id = interpreter.run("interpreter_b", event, company, announcement_text, snapshot, engine)
    _, run_d_id, decision, confidence, upside_pct, reasoning, missing_information = decider.run(
        event, company, thesis, interp_a, interp_b, announcement_text, engine,
        pre_ann_context=pre_ann_context,
    )

    logger.info(
        "Ensemble result for %s %s: %s (confidence=%.2f, upside=%.1f%%)",
        company.name, event.fiscal_period, decision, confidence or 0, upside_pct or 0,
    )
    return EnsembleResult(
        decision=decision,
        confidence=confidence,
        expected_upside_pct=upside_pct,
        reasoning_summary=reasoning,
        missing_information=missing_information,
        announcement_run_id=run_ann_id,
        interpreter_a_run_id=run_a_id,
        interpreter_b_run_id=run_b_id,
        decider_run_id=run_d_id,
    )
