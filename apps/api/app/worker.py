from __future__ import annotations

import argparse

from app.db.session import SessionLocal
from app.services.screening import process_next_screening_job


def run_pending_screening_jobs(*, once: bool = False) -> int:
    processed = 0
    while True:
        with SessionLocal() as db:
            job = process_next_screening_job(db)
            if job is None:
                db.commit()
                break
            processed += 1
            db.commit()
        if once:
            break
    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run pending hiring screening jobs.")
    parser.add_argument("--once", action="store_true", help="Process at most one pending screening job.")
    args = parser.parse_args()
    processed = run_pending_screening_jobs(once=args.once)
    print(f"processed={processed}")


if __name__ == "__main__":
    main()
