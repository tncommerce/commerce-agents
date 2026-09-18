from __future__ import annotations

import argparse
import json
from pathlib import Path

from .merchant_job_approval_runner import (
    MerchantJobApprovalResult,
    approve_job_from_fresh_dry_run,
)
from .merchant_jobs import (
    get_merchant_job,
    load_merchant_jobs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Explicitly approve one SCENTAI merchant job "
            "after a fresh clean dry-run."
        )
    )
    parser.add_argument("job_id")
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
        default=Path(
            "examples/retail/data/"
            "merchant_job_approvals.json"
        ),
    )
    parser.add_argument(
        "--confirm-human-approval",
        action="store_true",
        help=(
            "Explicit confirmation that a human approved "
            "the transition toward write mode."
        ),
    )

    args = parser.parse_args()

    if not args.confirm_human_approval:
        result = MerchantJobApprovalResult(
            action="hold",
            exit_code=20,
            reasons=[
                "explicit_human_confirmation_required"
            ],
        )

        print(
            json.dumps(
                result.model_dump(mode="json"),
                ensure_ascii=False,
            )
        )

        return result.exit_code

    jobs = load_merchant_jobs(args.jobs)
    job = get_merchant_job(
        jobs,
        args.job_id,
    )

    result = approve_job_from_fresh_dry_run(
        job,
        approvals_path=args.approvals,
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
