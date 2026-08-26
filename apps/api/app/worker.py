from __future__ import annotations

import argparse
import logging
import signal
import threading

from app.db.session import SessionLocal
from app.services.bulk_screening import process_next_bulk_screening_jobs
from app.services.screening import process_next_screening_job

logger = logging.getLogger(__name__)


def run_pending_screening_jobs(
    *,
    once: bool = False,
    poll_interval_seconds: float = 2.0,
    max_poll_interval_seconds: float = 30.0,
    stop_event: threading.Event | None = None,
    max_idle_cycles: int | None = None,
) -> int:
    processed = 0
    idle_cycles = 0
    current_sleep = poll_interval_seconds
    while True:
        job = None
        bulk_processed = 0
        if stop_event is not None and stop_event.is_set():
            break
        try:
            with SessionLocal() as db:
                job = process_next_screening_job(db)
                if job is None:
                    bulk_processed = process_next_bulk_screening_jobs(db)
                if job is None and bulk_processed == 0:
                    db.commit()
                    if once:
                        break
                    idle_cycles += 1
                    if max_idle_cycles is not None and idle_cycles >= max_idle_cycles:
                        break
                else:
                    processed += (1 if job is not None else 0) + bulk_processed
                    idle_cycles = 0
                    current_sleep = poll_interval_seconds
                    db.commit()
        except Exception:
            logger.exception("Screening worker loop iteration failed")
            idle_cycles += 1

        if once:
            break
        if (job is None and bulk_processed == 0) or idle_cycles:
            if stop_event is not None and stop_event.wait(current_sleep):
                break
            if max_idle_cycles is not None and idle_cycles >= max_idle_cycles:
                break
            current_sleep = min(max(current_sleep * 1.5, poll_interval_seconds), max_poll_interval_seconds)
    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run pending hiring screening jobs.")
    parser.add_argument("--once", action="store_true", help="Process at most one pending screening job.")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds to wait before polling an idle queue.",
    )
    parser.add_argument("--max-poll-interval", type=float, default=30.0, help="Maximum idle backoff in seconds.")
    args = parser.parse_args()
    stop_event = threading.Event()

    def stop_worker(signum, frame):  # noqa: ARG001
        stop_event.set()

    signal.signal(signal.SIGINT, stop_worker)
    signal.signal(signal.SIGTERM, stop_worker)
    processed = run_pending_screening_jobs(
        once=args.once,
        poll_interval_seconds=args.poll_interval,
        max_poll_interval_seconds=args.max_poll_interval,
        stop_event=stop_event,
    )
    print(f"processed={processed}")


if __name__ == "__main__":
    main()
