import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from db import bootstrap, get_engine
from universe.loader import sync_companies

if __name__ == "__main__":
    engine = get_engine()
    bootstrap(engine)
    count = sync_companies(engine)
    print(f"Synced {count} companies.")
