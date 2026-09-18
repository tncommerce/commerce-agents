from retail.api.merchant_job_status_summary import (
    MerchantJobStatusSummary,
)
from retail.api.merchant_operator_guidance import (
    build_job_attention_item,
)


def _summary(**updates):
    payload = {
        "job_id": "notino-de",
        "enabled": True,
        "job_state": "ready",
        "provider": "canonical",
        "feed_file": "feed.json",
        "dry_run": True,
        "readiness_reasons": [],
        "approval_required": False,
        "approval_present": False,
        "latest_run_reasons": [],
    }

    payload.update(updates)

    return MerchantJobStatusSummary(**payload)


def test_ready_job_has_no_operator_guidance() -> None:
    assert build_job_attention_item(_summary()) is None


def test_missing_feed_returns_safe_action() -> None:
    item = build_job_attention_item(
        _summary(
            job_state="not_ready",
            readiness_reasons=["feed_missing"],
        )
    )

    assert item is not None
    assert item.blocking is True
    assert item.reasons == ["feed_missing"]
    assert item.operator_actions == ["provide_feed"]


def test_missing_approval_returns_human_approval_action() -> None:
    item = build_job_attention_item(
        _summary(
            job_state="approval_required",
            dry_run=False,
            approval_required=True,
        )
    )

    assert item is not None
    assert item.blocking is True
    assert item.reasons == ["approval_required"]
    assert item.operator_actions == ["review_dry_run_and_approve"]


def test_review_run_returns_nonblocking_review_actions() -> None:
    item = build_job_attention_item(
        _summary(
            latest_run_status="review",
            latest_run_reasons=[
                "unmatched_rows",
                "invalid_rows",
            ],
        )
    )

    assert item is not None
    assert item.blocking is False
    assert item.reasons == [
        "unmatched_rows",
        "invalid_rows",
    ]
    assert item.operator_actions == [
        "review_unmatched_product_mappings",
        "review_invalid_feed_rows",
    ]
