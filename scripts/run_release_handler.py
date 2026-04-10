import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from db import bootstrap, get_engine
from pipeline.release_handler import scan_recent_news

if __name__ == "__main__":
    engine = get_engine()
    bootstrap(engine)
    decisions = scan_recent_news(engine, hours=1)
    print(f"Release handler: {len(decisions)} trade decision(s) written.")
    for d in decisions:
        print(f"  event={d.earnings_event_id} decision={d.decision} confidence={d.confidence}")
