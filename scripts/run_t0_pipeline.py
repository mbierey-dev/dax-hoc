import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from db import bootstrap, get_engine
from pipeline.t0_runner import run

if __name__ == "__main__":
    engine = get_engine()
    bootstrap(engine)
    decisions = run(engine)
    print(f"T0 pipeline: {len(decisions)} decision(s) made.")
