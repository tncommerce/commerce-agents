from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from .merchant_job_approval import revoke_job_approval
from .merchant_jobs import (
    MerchantJobProfile,
    get_merchant_job,
    load_merchant_jobs,
)


class MerchantJobDeactivationResult(BaseModel):
    action: str
    exit_code: int
    reasons: list[str]
    job_id: str
    approval_revoked: bool


def deactivate_merchant_job(
    *,
    jobs_path: Path,
    approvals_path: Path,
    job_id: str,
) -> MerchantJobDeactivationResult:
    jobs = load_merchant_jobs(jobs_path)
    job = get_merchant_job(
        jobs,
        job_id,
    )

    updated_jobs: list[MerchantJobProfile] = []

    for item in jobs:
        if item.job_id.strip().casefold() == job.job_id.strip().casefold():
            safe_config = item.config.model_copy(update={"dry_run": True})

            updated_jobs.append(
                item.model_copy(
                    update={
                        "enabled": False,
                        "config": safe_config,
                    }
                )
            )
        else:
            updated_jobs.append(item)

    payload = {"jobs": [item.model_dump(mode="json") for item in updated_jobs]}

    jobs_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    revoked = revoke_job_approval(
        approvals_path,
        job.job_id,
    )

    return MerchantJobDeactivationResult(
        action="deactivated",
        exit_code=0,
        reasons=[],
        job_id=job.job_id,
        approval_revoked=revoked,
    )
