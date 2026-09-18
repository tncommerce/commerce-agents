from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from .merchant_job_approval import (
    approval_matches_job,
    load_job_approvals,
)
from .merchant_job_readiness import evaluate_job_readiness
from .merchant_operational_runner import MerchantOperationalRun
from .merchant_scheduled_execution import (
    ScheduledMerchantImportConfig,
    run_scheduled_import,
)


class MerchantJobProfile(BaseModel):
    job_id: str
    enabled: bool = False
    config: ScheduledMerchantImportConfig


def load_merchant_jobs(
    path: Path,
) -> list[MerchantJobProfile]:
    raw = json.loads(
        path.read_text(encoding="utf-8-sig")
    )
    rows = raw.get("jobs", [])

    jobs = [
        MerchantJobProfile.model_validate(row)
        for row in rows
    ]

    normalized_ids = [
        job.job_id.strip().casefold()
        for job in jobs
    ]

    if len(normalized_ids) != len(set(normalized_ids)):
        raise ValueError("Duplicate merchant job_id")

    return jobs


def get_merchant_job(
    jobs: list[MerchantJobProfile],
    job_id: str,
) -> MerchantJobProfile:
    key = job_id.strip().casefold()

    for job in jobs:
        if job.job_id.strip().casefold() == key:
            return job

    raise KeyError(
        f"Unknown merchant job: {job_id}"
    )


def run_merchant_job(
    jobs: list[MerchantJobProfile],
    job_id: str,
    *,
    approvals_path: Path | None = None,
) -> MerchantOperationalRun:
    job = get_merchant_job(
        jobs,
        job_id,
    )

    if not job.enabled:
        return MerchantOperationalRun(
            action="hold",
            exit_code=20,
            import_exit_code=20,
            reasons=["job_disabled"],
        )

    readiness = evaluate_job_readiness(job.config)

    if not readiness.ready:
        return MerchantOperationalRun(
            action="hold",
            exit_code=20,
            import_exit_code=20,
            reasons=[
                "job_not_ready",
                *readiness.reasons,
            ],
        )

    if not job.config.dry_run:
        approval_file = (
            approvals_path
            if approvals_path is not None
            else Path(
                "examples/retail/data/"
                "merchant_job_approvals.json"
            )
        )

        approvals = load_job_approvals(
            approval_file
        )

        approved = any(
            approval_matches_job(
                approval,
                job_id=job.job_id,
                config=job.config,
            )
            for approval in approvals
        )

        if not approved:
            return MerchantOperationalRun(
                action="hold",
                exit_code=20,
                import_exit_code=20,
                reasons=[
                    "dry_run_approval_required"
                ],
            )

    return run_scheduled_import(job.config)
