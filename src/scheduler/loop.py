"""Entrypoint for the `scheduler` container: repeatedly runs a watchlist
check on a fixed interval. This is a plain loop rather than cron inside the
container -- a single long-running foreground process is the standard,
simplest pattern for a scheduled task in Docker (no cron daemon, no extra
process supervisor, container logs are just stdout).
"""

import logging
import os
import time

from src.scheduler.run import run_watchlist_check
from src.storage.db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 3600


def main() -> None:
    interval = int(os.environ.get("SCHEDULER_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS))

    # The scheduler is a separate container/process from the backend, so it
    # can't assume the backend has already created the schema -- init_db()
    # uses CREATE TABLE IF NOT EXISTS, so this is a safe no-op if the
    # backend already did it against the same shared DB_PATH volume.
    init_db()

    logger.info("Scheduler starting, interval=%ss", interval)

    while True:
        try:
            result = run_watchlist_check()
            logger.info("Watchlist check complete: %s", result)
        except Exception:
            logger.exception("Scheduled watchlist check failed")

        time.sleep(interval)


if __name__ == "__main__":
    main()
