import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ── Preserved from original ──────────────────────────────────────────────────


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at_utc: Mapped[datetime | None] = mapped_column(DateTime)
    category: Mapped[str | None] = mapped_column(String)
    category_code: Mapped[str | None] = mapped_column(String)
    company_name: Mapped[str | None] = mapped_column(String)
    company_uuid: Mapped[str | None] = mapped_column(String)
    isin: Mapped[str | None] = mapped_column(String)
    headline: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String)
    locale: Mapped[str | None] = mapped_column(String)
    timezone: Mapped[str | None] = mapped_column(String)
    content: Mapped[str | None] = mapped_column(Text)
    share_url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    raw_json: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<NewsItem {self.id} | {self.company_name}: {(self.headline or '')[:60]}>"


# ── New tables ────────────────────────────────────────────────────────────────


class Company(Base):
    __tablename__ = "companies"

    isin: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    index_name: Mapped[str] = mapped_column(String)  # DAX / MDAX / SDAX
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
    expected_time_local: Mapped[time | None] = mapped_column(Time)
    time_confidence: Mapped[str] = mapped_column(
        String, default="unknown"
    )  # exact / estimated / unknown
    source: Mapped[str] = mapped_column(String, default="eqs_calendar")
    status: Mapped[str] = mapped_column(
        String, default="scheduled"
    )  # scheduled / released / cancelled / missed
    actual_release_at: Mapped[datetime | None] = mapped_column(DateTime)
    news_item_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("news_items.id")
    )
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
    interpreter_a_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("llm_runs.id")
    )
    interpreter_b_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("llm_runs.id")
    )
    reaction_run_id: Mapped[str | None] = mapped_column(
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
