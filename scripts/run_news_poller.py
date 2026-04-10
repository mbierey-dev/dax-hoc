import argparse
import asyncio
import logging
import signal

from eqs.news_poller import poll_loop

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EQS News Poller")
    parser.add_argument("--interval", type=int, default=30, help="Poll interval in seconds")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    loop = asyncio.new_event_loop()

    def shutdown(sig, _frame):
        logging.info("Received %s, shutting down...", signal.Signals(sig).name)
        for task in asyncio.all_tasks(loop):
            task.cancel()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        loop.run_until_complete(poll_loop(args.interval))
    except asyncio.CancelledError:
        pass
    finally:
        loop.close()
        logging.info("Poller stopped.")
