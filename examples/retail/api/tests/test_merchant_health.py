from retail.api.merchant_health import (
    evaluate_job_health,
)
from retail.api.merchant_job_status_summary import (
    MerchantJobStatusSummary,
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

    return MerchantJobStatusSummary(
        **payload
    )


def test_ready_job_health_is_ok() -> None:
    health = evaluate_job_health(
        _summary()
    )

    assert health.severity == "ok"
    assert health.reasons == []


def test_disabled_job_health_is_info() -> None:
    health = evaluate_job_health(
        _summary(
            enabled=False,
            job_state="disabled",
        )
    )

    assert health.severity == "info"
    assert health.reasons == [
        "job_disabled"
    ]


def test_not_ready_job_health_is_blocked() -> None:
    health = evaluate_job_health(
        _summary(
            job_state="not_ready",
            readiness_reasons=[
                "feed_missing"
            ],
        )
    )

    assert health.severity == "blocked"
    assert health.reasons == [
        "feed_missing"
    ]


def test_review_run_health_is_warning() -> None:
    health = evaluate_job_health(
        _summary(
            latest_run_status="review",
            latest_run_reasons=[
                "unmatched_rows"
            ],
        )
    )

    assert health.severity == "warning"
    assert health.reasons == [
        "unmatched_rows"
    ]


def test_missing_approval_health_is_blocked() -> None:
    health = evaluate_job_health(
        _summary(
            job_state="approval_required",
            dry_run=False,
            approval_required=True,
        )
    )

    assert health.severity == "blocked"
    assert health.reasons == [
        "approval_required"
    ]
