from __future__ import annotations

import argparse
import json
from pathlib import Path

from .merchant_job_activation import (
    MerchantJobActivationResult,
    activate_merchant_job,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=("Activate one approved SCENTAI merchant job for write execution.")
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
        default=Path("examples/retail/data/merchant_job_approvals.json"),
    )

    parser.add_argument(
        "--confirm-human-activation",
        action="store_true",
        help=("Explicit human confirmation for switching the job from dry-run to write mode."),
    )

    args = parser.parse_args()

    if not args.confirm_human_activation:
        result = MerchantJobActivationResult(
            action="hold",
            exit_code=20,
            reasons=["explicit_human_activation_required"],
            job_id=args.job_id,
        )
    else:
        result = activate_merchant_job(
            jobs_path=args.jobs,
            approvals_path=args.approvals,
            job_id=args.job_id,
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
