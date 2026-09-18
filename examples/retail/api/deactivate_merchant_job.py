from __future__ import annotations

import argparse
import json
from pathlib import Path

from .merchant_job_deactivation import (
    MerchantJobDeactivationResult,
    deactivate_merchant_job,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=("Safely deactivate one SCENTAI merchant job and revoke its write approval.")
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
        "--confirm-human-deactivation",
        action="store_true",
        help=("Explicit human confirmation for disabling the merchant job and revoking approval."),
    )

    args = parser.parse_args()

    if not args.confirm_human_deactivation:
        result = MerchantJobDeactivationResult(
            action="hold",
            exit_code=20,
            reasons=["explicit_human_deactivation_required"],
            job_id=args.job_id,
            approval_revoked=False,
        )
    else:
        result = deactivate_merchant_job(
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
