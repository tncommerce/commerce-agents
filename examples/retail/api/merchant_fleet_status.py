from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from .merchant_job_status_summary import (
    DEFAULT_APPROVALS_PATH,
    MerchantJobStatusSummary,
    build_job_status_summary,
)
from .merchant_jobs import MerchantJobProfile
from .merchant_operator_guidance import (
    MerchantJobAttentionItem,
    build_job_attention_item,
)


class MerchantFleetStatusSummary(BaseModel):
    total_jobs: int

    ready: int
    disabled: int
    not_ready: int
    approval_required: int

    latest_run_review: int

    attention_required: int
    attention_job_ids: list[str]
    attention_items: list[MerchantJobAttentionItem]

    jobs: list[MerchantJobStatusSummary]


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

    attention_items = []

    for summary in summaries:
        item = build_job_attention_item(
            summary
        )

        if item is not None:
            attention_items.append(item)

    attention_job_ids = [
        item.job_id
        for item in attention_items
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
        attention_required=len(attention_items),
        attention_job_ids=attention_job_ids,
        attention_items=attention_items,
        jobs=summaries,
    )
