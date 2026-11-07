"""Background worker entry point. Skeleton: polls outbox table for tasks."""

import asyncio
import signal

from app.core.config import settings
from app.core.logging import configure_logging, get_logger

logger = get_logger("worker")


async def run_worker() -> None:
    configure_logging()
    logger.info("worker_started")
    while True:
        # Skeleton: poll for outbox tasks. Real implementation in later tasks.
        await asyncio.sleep(5)


def main() -> None:
    loop = asyncio.new_event_loop()
    stop = asyncio.Event()

    def _shutdown(signum, frame):
        stop.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        loop.run_until_complete(asyncio.wait_for(run_worker(), timeout=None))
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        logger.info("worker_stopped")
        loop.close()


if __name__ == "__main__":
    main()
