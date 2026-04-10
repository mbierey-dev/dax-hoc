"""
Fixture-based test for EarningsEvent creation.

The `sap_event` fixture produces a fully-populated EarningsEvent (+ its parent
Company row) in an isolated in-memory DB.  It is intentionally reusable — later
tests for the researcher, ensemble, and pipeline can import and build on it.
"""
import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db.models import Base, Company, EarningsEvent


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def engine():
    """In-memory SQLite engine with all tables created."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture
def sap_company(session):
    """SAP SE as a Company row — parent required by the EarningsEvent FK."""
    company = Company(
        isin="DE0007164600",
        name="SAP SE",
        index_name="DAX",
        industry="Enterprise Software",
        description="World's largest enterprise software company.",
        synced_at=datetime.now(timezone.utc),
    )
    session.add(company)
    session.commit()
    return company


@pytest.fixture
def sap_event(session, sap_company):
    """
    A realistic Q1 2026 EarningsEvent for SAP SE.

    This is the canonical test object for exercising the researcher,
    ensemble pipeline, and release handler in future tests.
    """
    event = EarningsEvent(
        id=str(uuid.uuid4()),
        isin="DE0007164600",
        fiscal_period="2026-Q1",
        event_type="quarterly",
        expected_date=date(2026, 4, 23),
        expected_time_local=None,
        time_confidence="exact",
        source="yahoo_finance",
        status="scheduled",
        actual_release_at=None,
        news_item_id=None,
        last_synced_at=datetime.now(timezone.utc),
    )
    session.add(event)
    session.commit()
    return event


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_event_persisted(session, sap_event):
    """Event is stored and retrievable by its primary key."""
    loaded = session.get(EarningsEvent, sap_event.id)
    assert loaded is not None
    assert loaded.isin == "DE0007164600"
    assert loaded.fiscal_period == "2026-Q1"


def test_event_fields(sap_event):
    """All fields are set as expected."""
    assert sap_event.expected_date == date(2026, 4, 23)
    assert sap_event.event_type == "quarterly"
    assert sap_event.time_confidence == "exact"
    assert sap_event.source == "yahoo_finance"
    assert sap_event.status == "scheduled"
    assert sap_event.actual_release_at is None


def test_unique_constraint(session, sap_event):
    """Inserting a second event with the same (isin, fiscal_period) raises."""
    from sqlalchemy.exc import IntegrityError

    duplicate = EarningsEvent(
        id=str(uuid.uuid4()),
        isin="DE0007164600",
        fiscal_period="2026-Q1",
        event_type="quarterly",
        expected_date=date(2026, 4, 23),
        time_confidence="exact",
        source="yahoo_finance",
        status="scheduled",
        last_synced_at=datetime.now(timezone.utc),
    )
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        session.commit()


def test_status_transition(session, sap_event):
    """Marking an event as released updates status and actual_release_at."""
    release_time = datetime(2026, 4, 23, 7, 0, tzinfo=timezone.utc)
    sap_event.status = "released"
    sap_event.actual_release_at = release_time
    session.commit()

    reloaded = session.scalars(
        select(EarningsEvent).where(EarningsEvent.id == sap_event.id)
    ).one()
    assert reloaded.status == "released"
    # SQLite stores datetimes without timezone; compare naive
    assert reloaded.actual_release_at == release_time.replace(tzinfo=None)
