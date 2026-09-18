from __future__ import annotations

import argparse
import json
from pathlib import Path

from .merchant_fleet_status import (
    build_fleet_status_summary,
)
from .merchant_job_status_summary import (
    DEFAULT_APPROVALS_PATH,
)
from .merchant_jobs import (
    load_merchant_jobs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Show operational status for all "
            "SCENTAI merchant jobs."
        )
    )

    parser.add_argument(
        "--jobs",
        type=Path,
        default=Path(
            "examples/retail/data/merchant_jobs.json"
        ),
    )

    parser.add_argument(
        "--approvals",
        type=Path,
        default=DEFAULT_APPROVALS_PATH,
    )

    args = parser.parse_args()

    jobs = load_merchant_jobs(args.jobs)

    summary = build_fleet_status_summary(
        jobs,
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
