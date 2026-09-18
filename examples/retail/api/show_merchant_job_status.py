from __future__ import annotations

import argparse
import json
from pathlib import Path

from .merchant_job_status_summary import (
    DEFAULT_APPROVALS_PATH,
    build_job_status_summary,
)
from .merchant_jobs import (
    get_merchant_job,
    load_merchant_jobs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=("Show operational status for one SCENTAI merchant job.")
    )

    parser.add_argument("job_id")

    parser.add_argument(
        "--jobs",
        type=Path,
        default=Path("examples/retail/data/merchant_jobs.json"),
    )

    parser.add_argument(
        "--approvals",
        type=Path,
        default=DEFAULT_APPROVALS_PATH,
    )

    args = parser.parse_args()

    jobs = load_merchant_jobs(args.jobs)

    try:
        job = get_merchant_job(
            jobs,
            args.job_id,
        )
    except KeyError:
        parser.error(f"Unknown merchant job: {args.job_id}")

    summary = build_job_status_summary(
        job,
        approvals_path=args.approvals,
    )

    print(
        json.dumps(
            summary.model_dump(mode="json"),
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
