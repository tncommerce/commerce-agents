from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from .merchant_job_approval import (
    approval_matches_job,
    load_job_approvals,
)
from .merchant_job_readiness import evaluate_job_readiness
from .merchant_jobs import (
    MerchantJobProfile,
    get_merchant_job,
    load_merchant_jobs,
)


class MerchantJobActivationResult(BaseModel):
    action: str
    exit_code: int
    reasons: list[str]
    job_id: str


def activate_merchant_job(
    *,
    jobs_path: Path,
    approvals_path: Path,
    job_id: str,
) -> MerchantJobActivationResult:
    jobs = load_merchant_jobs(jobs_path)
    job = get_merchant_job(
        jobs,
        job_id,
    )

    if not job.config.dry_run:
        return MerchantJobActivationResult(
            action="hold",
            exit_code=20,
            reasons=["job_already_in_write_mode"],
            job_id=job.job_id,
        )

    readiness = evaluate_job_readiness(job.config)

    if not readiness.ready:
        return MerchantJobActivationResult(
            action="hold",
            exit_code=20,
            reasons=[
                "job_not_ready",
                *readiness.reasons,
            ],
            job_id=job.job_id,
        )

    approvals = load_job_approvals(
        approvals_path
    )

    matching = [
        approval
        for approval in approvals
        if approval_matches_job(
            approval,
            job_id=job.job_id,
            config=job.config,
        )
    ]

    if not matching:
        return MerchantJobActivationResult(
            action="hold",
            exit_code=20,
            reasons=["valid_approval_required"],
            job_id=job.job_id,
        )

    updated_jobs: list[MerchantJobProfile] = []

    for item in jobs:
        if (
            item.job_id.strip().casefold()
            == job.job_id.strip().casefold()
        ):
            updated_config = item.config.model_copy(
                update={"dry_run": False}
            )

            updated_jobs.append(
                item.model_copy(
                    update={
                        "enabled": True,
                        "config": updated_config,
                    }
                )
            )
        else:
            updated_jobs.append(item)

    payload = {
        "jobs": [
            item.model_dump(mode="json")
            for item in updated_jobs
        ]
    }

    jobs_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return MerchantJobActivationResult(
        action="activated",
        exit_code=0,
        reasons=[],
        job_id=job.job_id,
    )
