from __future__ import annotations

import argparse
import json
from pathlib import Path

from .merchant_jobs import (
    load_merchant_jobs,
    run_merchant_job,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one configured SCENTAI merchant job.")
    parser.add_argument("job_id")
    parser.add_argument(
        "--jobs",
        type=Path,
        default=Path("examples/retail/data/merchant_jobs.json"),
    )

    args = parser.parse_args()

    jobs = load_merchant_jobs(args.jobs)
    result = run_merchant_job(
        jobs,
        args.job_id,
    )

    print(
        json.dumps(
            result.model_dump(mode="json"),
            ensure_ascii=False,
        )
    )

    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
