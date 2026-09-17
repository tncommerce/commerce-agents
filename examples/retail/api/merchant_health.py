from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .merchant_job_status_summary import (
    MerchantJobStatusSummary,
)
from .merchant_operator_guidance import (
    build_job_attention_item,
)


HealthSeverity = Literal[
    "ok",
    "info",
    "warning",
    "blocked",
]


class MerchantJobHealth(BaseModel):
    job_id: str
    severity: HealthSeverity
    reasons: list[str]


def evaluate_job_health(
    summary: MerchantJobStatusSummary,
) -> MerchantJobHealth:
    if not summary.enabled:
        return MerchantJobHealth(
            job_id=summary.job_id,
            severity="info",
            reasons=["job_disabled"],
        )

    attention = build_job_attention_item(
        summary
    )

    if attention is None:
        return MerchantJobHealth(
            job_id=summary.job_id,
            severity="ok",
            reasons=[],
        )

    if attention.blocking:
        severity: HealthSeverity = "blocked"
    else:
        severity = "warning"

    return MerchantJobHealth(
        job_id=summary.job_id,
        severity=severity,
        reasons=attention.reasons,
    )
