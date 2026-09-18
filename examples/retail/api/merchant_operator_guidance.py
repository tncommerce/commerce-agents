from __future__ import annotations

from pydantic import BaseModel

from .merchant_job_status_summary import (
    MerchantJobStatusSummary,
)


class MerchantJobAttentionItem(BaseModel):
    job_id: str
    blocking: bool
    reasons: list[str]
    operator_actions: list[str]


_REASON_ACTIONS = {
    "feed_missing": "provide_feed",
    "mappings_missing": "provide_mappings",
    "unsupported_provider": "configure_supported_provider",
    "incomplete_authoritative_scope": "fix_authoritative_scope",
    "approval_required": "review_dry_run_and_approve",
    "unmatched_rows": "review_unmatched_product_mappings",
    "invalid_rows": "review_invalid_feed_rows",
    "offers_deactivated": "review_deactivated_offers",
}


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def build_job_attention_item(
    summary: MerchantJobStatusSummary,
) -> MerchantJobAttentionItem | None:
    if not summary.enabled:
        return None

    reasons: list[str] = []

    if summary.job_state == "not_ready":
        reasons.extend(
            summary.readiness_reasons
        )

    if summary.job_state == "approval_required":
        reasons.append(
            "approval_required"
        )

    if summary.latest_run_status == "review":
        reasons.extend(
            summary.latest_run_reasons
        )

    reasons = _unique(reasons)

    if not reasons:
        return None

    actions = _unique(
        [
            _REASON_ACTIONS.get(
                reason,
                "manual_review_required",
            )
            for reason in reasons
        ]
    )

    return MerchantJobAttentionItem(
        job_id=summary.job_id,
        blocking=summary.job_state in (
            "not_ready",
            "approval_required",
        ),
        reasons=reasons,
        operator_actions=actions,
    )
