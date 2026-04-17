import csv
import logging
from datetime import datetime, timezone

from sqlalchemy.dialects.sqlite import insert

from config import UNIVERSE_CSV
from db import get_session
from db.models import Company

logger = logging.getLogger(__name__)


def _read_universe() -> list[dict]:
    """
    Read tradeable_universe.csv robustly. The description column is unquoted and may
    contain commas, so we rejoin any overflow fields back into the description.
    """
    rows = []
    with open(UNIVERSE_CSV, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if len(row) < 5:
                continue
            rows.append(
                {
                    "company_name": row[0].strip(),
                    "ISIN": row[1].strip(),
                    "ticker": row[2].strip() or None,
                    "index": row[3].strip(),
                    "industry": row[4].strip(),
                    "description": ",".join(row[5:]).strip() if len(row) > 5 else None,
                }
            )
    return rows


def sync_companies(engine) -> int:
    """Load tradeable_universe.csv and upsert into the companies table. Returns row count."""
    rows = _read_universe()
    now = datetime.now(timezone.utc)

    records = [
        {
            "isin": row["ISIN"],
            "name": row["company_name"],
            "ticker": row["ticker"],
            "index_name": row["index"],
            "industry": row["industry"],
            "description": row["description"],
            "synced_at": now,
        }
        for row in rows
    ]

    session = get_session(engine)
    try:
        stmt = insert(Company).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["isin"],
            set_={
                "name": stmt.excluded.name,
                "ticker": stmt.excluded.ticker,
                "index_name": stmt.excluded.index_name,
                "industry": stmt.excluded.industry,
                "description": stmt.excluded.description,
                "synced_at": stmt.excluded.synced_at,
            },
        )
        session.execute(stmt)
        session.commit()
    finally:
        session.close()

    logger.info("Synced %d companies from %s", len(records), UNIVERSE_CSV.name)
    return len(records)
