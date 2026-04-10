import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from db import bootstrap, get_engine
from earnings.calendar_sync import LOOKAHEAD_DAYS, sync_all

if __name__ == "__main__":
    engine = get_engine()
    bootstrap(engine)
    events = sync_all(engine)
    print(f"\nFound {len(events)} confirmed earnings event(s) in the next {LOOKAHEAD_DAYS} days:")
    for ev in sorted(events, key=lambda e: e["expected_date"]):
        print(f"  {ev['expected_date']}  {ev['isin']}  [{ev['fiscal_period']}]")
