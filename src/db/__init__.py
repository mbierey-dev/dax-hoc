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


def bootstrap(engine=None) -> None:
    """Create all tables that don't yet exist. Safe to call on every startup."""
    from db.models import Base

    engine = engine or get_engine()
    Base.metadata.create_all(engine)
