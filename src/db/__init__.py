import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from config import DB_PATH


def get_engine():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{DB_PATH}", echo=False)


def get_session(engine=None) -> Session:
    engine = engine or get_engine()
    return sessionmaker(bind=engine)()


def read_all(engine=None) -> dict[str, pd.DataFrame]:
    """Return every table in the DB as a dict of {table_name: DataFrame}."""
    engine = engine or get_engine()
    table_names = inspect(engine).get_table_names()
    return {name: pd.read_sql(text(f"SELECT * FROM {name}"), engine) for name in table_names}


def delete_rows(table: str, ids: list[int], engine=None) -> int:
    """Delete rows by ID from a table. Returns the number of rows deleted."""
    engine = engine or get_engine()
    placeholders = ", ".join(f":id{i}" for i in range(len(ids)))
    params = {f"id{i}": v for i, v in enumerate(ids)}
    with engine.begin() as conn:
        result = conn.execute(text(f"DELETE FROM {table} WHERE id IN ({placeholders})"), params)
    return result.rowcount


def bootstrap(engine=None) -> None:
    """Create all tables that don't yet exist. Safe to call on every startup."""
    from db.models import Base, PriceReaction

    engine = engine or get_engine()

    insp = inspect(engine)
    if insp.has_table("price_reactions"):
        existing = {c["name"] for c in insp.get_columns("price_reactions")}
        if "abnormal_return_t0" not in existing:
            PriceReaction.__table__.drop(engine)

    if insp.has_table("earnings_events"):
        existing = {c["name"] for c in insp.get_columns("earnings_events")}
        if "actual_release_at" not in existing:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE earnings_events ADD COLUMN actual_release_at DATETIME"))

    if insp.has_table("expectations_snapshots"):
        existing = {c["name"] for c in insp.get_columns("expectations_snapshots")}
        if "pre_ann_ticker" not in existing:
            with engine.begin() as conn:
                for col, typ in [
                    ("pre_ann_ticker", "VARCHAR"),
                    ("pre_ann_return_1d", "FLOAT"),
                    ("pre_ann_return_3d", "FLOAT"),
                    ("pre_ann_return_7d", "FLOAT"),
                    ("pre_ann_abnormal_return_1d", "FLOAT"),
                    ("pre_ann_abnormal_return_3d", "FLOAT"),
                    ("pre_ann_abnormal_return_7d", "FLOAT"),
                    ("pre_ann_fetched_at", "DATETIME"),
                ]:
                    conn.execute(text(f"ALTER TABLE expectations_snapshots ADD COLUMN {col} {typ}"))

    Base.metadata.create_all(engine)
