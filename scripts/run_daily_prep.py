import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from db import bootstrap, get_engine
from pipeline.daily_prep import run

if __name__ == "__main__":
    engine = get_engine()
    bootstrap(engine)
    count = run(engine)
    print(f"Daily prep: {count} event(s) prepared.")
