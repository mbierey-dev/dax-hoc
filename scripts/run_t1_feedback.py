import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from db import bootstrap, get_engine  # noqa: E402
from pipeline.t1_feedback import run  # noqa: E402

if __name__ == "__main__":
    engine = get_engine()
    bootstrap(engine)
    count = run(engine)
    print(f"T+1 feedback: {count} report(s) created.")
