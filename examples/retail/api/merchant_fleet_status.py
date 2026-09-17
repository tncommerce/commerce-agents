from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from .merchant_job_status_summary import (
    DEFAULT_APPROVALS_PATH,
    MerchantJobStatusSummary,
    build_job_status_summary,
)
from .merchant_jobs import MerchantJobProfile


class MerchantFleetStatusSummary(BaseModel):
    total_jobs: int

    ready: int
    disabled: int
    not_ready: int
    approval_required: int

    latest_run_review: int

    attention_required: int
    attention_job_ids: list[str]

    jobs: list[MerchantJobStatusSummary]


def _needs_attention(
    summary: MerchantJobStatusSummary,
) -> bool:
    if not summary.enabled:
        return False

    if summary.job_state in (
        "not_ready",
        "approval_required",
    ):
        return True

    return summary.latest_run_status == "review"


def build_fleet_status_summary(
    jobs: list[MerchantJobProfile],
    *,
    approvals_path: Path = DEFAULT_APPROVALS_PATH,
) -> MerchantFleetStatusSummary:
    summaries = [
        build_job_status_summary(
            job,
            approvals_path=approvals_path,
        )
        for job in jobs
    ]

    summaries.sort(
        key=lambda summary: summary.job_id.casefold()
    )

    attention_job_ids = [
        summary.job_id
        for summary in summaries
        if _needs_attention(summary)
    ]

    return MerchantFleetStatusSummary(
        total_jobs=len(summaries),
        ready=sum(
            summary.job_state == "ready"
            for summary in summaries
        ),
        disabled=sum(
            summary.job_state == "disabled"
            for summary in summaries
        ),
        not_ready=sum(
            summary.job_state == "not_ready"
            for summary in summaries
        ),
        approval_required=sum(
            summary.job_state == "approval_required"
            for summary in summaries
        ),
        latest_run_review=sum(
            summary.latest_run_status == "review"
            for summary in summaries
        ),
        attention_required=len(attention_job_ids),
        attention_job_ids=attention_job_ids,
        jobs=summaries,
    )
