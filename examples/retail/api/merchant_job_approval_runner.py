from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ValidationError

from .merchant_automation import MerchantMachineResult
from .merchant_job_approval import (
    build_job_approval,
    upsert_job_approval,
)
from .merchant_job_readiness import evaluate_job_readiness
from .merchant_jobs import MerchantJobProfile
from .merchant_scheduled_execution import run_scheduled_import


class MerchantJobApprovalResult(BaseModel):
    action: Literal["approved", "hold"]
    exit_code: int
    reasons: list[str]
    approved_run_id: str | None = None


def approve_job_from_fresh_dry_run(
    job: MerchantJobProfile,
    *,
    approvals_path,
) -> MerchantJobApprovalResult:
    if not job.config.dry_run:
        return MerchantJobApprovalResult(
            action="hold",
            exit_code=20,
            reasons=["job_not_in_dry_run_mode"],
        )

    readiness = evaluate_job_readiness(job.config)

    if not readiness.ready:
        return MerchantJobApprovalResult(
            action="hold",
            exit_code=20,
            reasons=[
                "job_not_ready",
                *readiness.reasons,
            ],
        )

    operational = run_scheduled_import(job.config)

    if (
        operational.action != "continue"
        or operational.exit_code != 0
        or operational.payload is None
        or operational.run_id is None
    ):
        return MerchantJobApprovalResult(
            action="hold",
            exit_code=20,
            reasons=[
                "dry_run_not_clean",
                *operational.reasons,
            ],
        )

    try:
        machine = MerchantMachineResult.model_validate(operational.payload)
    except ValidationError:
        return MerchantJobApprovalResult(
            action="hold",
            exit_code=20,
            reasons=["invalid_dry_run_evidence"],
        )

    run = machine.run

    evidence_matches = (
        machine.status == "ok"
        and machine.exit_code == 0
        and run.run_id == operational.run_id
        and run.mode == "DRY-RUN"
        and run.provider.strip().casefold() == job.config.provider.strip().casefold()
        and run.feed_file == job.config.feed.name
        and run.authoritative_merchant_id == job.config.authoritative_merchant_id
        and run.authoritative_data_source == job.config.authoritative_data_source
    )

    if not evidence_matches:
        return MerchantJobApprovalResult(
            action="hold",
            exit_code=20,
            reasons=["dry_run_evidence_mismatch"],
        )

    approval = build_job_approval(
        job_id=job.job_id,
        approved_run_id=run.run_id,
        config=job.config,
    )

    upsert_job_approval(
        approvals_path,
        approval,
    )

    return MerchantJobApprovalResult(
        action="approved",
        exit_code=0,
        reasons=[],
        approved_run_id=run.run_id,
    )
