import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    isin: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    ticker: Mapped[str | None] = mapped_column(String)  # exchange ticker if ISIN lookup fails
    index_name: Mapped[str] = mapped_column(String)  # DAX / MDAX / SDAX / EURO STOXX 50
    industry: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    synced_at: Mapped[datetime] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return f"<Company {self.isin} {self.name} ({self.index_name})>"


class EarningsEvent(Base):
    __tablename__ = "earnings_events"
    __table_args__ = (UniqueConstraint("isin", "fiscal_period"),)

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    isin: Mapped[str] = mapped_column(
        String, ForeignKey("companies.isin"), nullable=False
    )
    fiscal_period: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "2026-Q1"
    event_type: Mapped[str] = mapped_column(String)  # quarterly / half_year / full_year
    expected_date: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String, default="yahoo_finance")
    status: Mapped[str] = mapped_column(
        String, default="scheduled"
    )  # scheduled / processed / cancelled
    actual_release_at: Mapped[datetime | None] = mapped_column(DateTime)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<EarningsEvent {self.isin} {self.fiscal_period} [{self.status}]>"


class LLMRun(Base):
    __tablename__ = "llm_runs"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    earnings_event_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("earnings_events.id")
    )
    role: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    prompt: Mapped[str | None] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(Text)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    cost_estimate: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow()
    )


class ExpectationsSnapshot(Base):
    __tablename__ = "expectations_snapshots"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    earnings_event_id: Mapped[str] = mapped_column(
        String, ForeignKey("earnings_events.id"), nullable=False
    )
    gathered_at: Mapped[datetime] = mapped_column(DateTime)
    narrative_md: Mapped[str | None] = mapped_column(Text)   # what the market expects + key watchpoints
    trade_thesis_md: Mapped[str | None] = mapped_column(Text)  # buy conditions for this specific event
    sources_json: Mapped[str | None] = mapped_column(Text)   # JSON list of URLs/citations
    raw_research_text: Mapped[str | None] = mapped_column(Text)
    llm_run_id: Mapped[str | None] = mapped_column(String, ForeignKey("llm_runs.id"))
    pre_ann_ticker: Mapped[str | None] = mapped_column(String)
    pre_ann_return_1d: Mapped[float | None] = mapped_column(Float)
    pre_ann_return_3d: Mapped[float | None] = mapped_column(Float)
    pre_ann_return_7d: Mapped[float | None] = mapped_column(Float)
    pre_ann_abnormal_return_1d: Mapped[float | None] = mapped_column(Float)
    pre_ann_abnormal_return_3d: Mapped[float | None] = mapped_column(Float)
    pre_ann_abnormal_return_7d: Mapped[float | None] = mapped_column(Float)
    pre_ann_fetched_at: Mapped[datetime | None] = mapped_column(DateTime)


class TradeDecision(Base):
    __tablename__ = "trade_decisions"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    earnings_event_id: Mapped[str] = mapped_column(
        String, ForeignKey("earnings_events.id"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String)  # buy / skip
    confidence: Mapped[float | None] = mapped_column(Float)  # 0.0–1.0
    expected_upside_pct: Mapped[float | None] = mapped_column(Float)
    reasoning_summary: Mapped[str | None] = mapped_column(Text)
    missing_information: Mapped[str | None] = mapped_column(Text)
    announcement_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("llm_runs.id")
    )
    interpreter_a_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("llm_runs.id")
    )
    interpreter_b_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("llm_runs.id")
    )
    decider_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("llm_runs.id")
    )
    expectations_snapshot_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("expectations_snapshots.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow()
    )


class PriceReaction(Base):
    __tablename__ = "price_reactions"
    __table_args__ = (UniqueConstraint("earnings_event_id"),)

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    earnings_event_id: Mapped[str] = mapped_column(
        String, ForeignKey("earnings_events.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String)  # symbol actually used with yfinance
    date_t_minus_1: Mapped[date] = mapped_column(Date)  # prior trading day
    date_t0: Mapped[date] = mapped_column(Date)  # announcement day
    close_t_minus_1: Mapped[float | None] = mapped_column(Float)
    close_t0: Mapped[float | None] = mapped_column(Float)
    return_t0: Mapped[float | None] = mapped_column(Float)  # (close_t0/close_t_minus_1)-1
    benchmark_ticker: Mapped[str | None] = mapped_column(String)
    benchmark_close_t_minus_1: Mapped[float | None] = mapped_column(Float)
    benchmark_close_t0: Mapped[float | None] = mapped_column(Float)
    benchmark_return_t0: Mapped[float | None] = mapped_column(Float)
    abnormal_return_t0: Mapped[float | None] = mapped_column(Float)  # return_t0 - benchmark_return_t0
    fetched_at: Mapped[datetime] = mapped_column(DateTime)


class FeedbackReport(Base):
    __tablename__ = "feedback_reports"
    __table_args__ = (UniqueConstraint("trade_decision_id"),)

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    earnings_event_id: Mapped[str] = mapped_column(
        String, ForeignKey("earnings_events.id"), nullable=False
    )
    trade_decision_id: Mapped[str] = mapped_column(
        String, ForeignKey("trade_decisions.id"), nullable=False
    )
    price_reaction_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("price_reactions.id")
    )
    decision_correct: Mapped[str | None] = mapped_column(String)  # correct / incorrect / partial
    key_learnings_md: Mapped[str | None] = mapped_column(Text)
    improvement_suggestions_md: Mapped[str | None] = mapped_column(Text)
    market_narrative_md: Mapped[str | None] = mapped_column(Text)
    raw_feedback_text: Mapped[str | None] = mapped_column(Text)
    llm_run_id: Mapped[str | None] = mapped_column(String, ForeignKey("llm_runs.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow()
    )
