from retail.api.merchant_run_reports import build_import_run_report
from retail.api.merchant_run_status import (
    evaluate_import_run,
    machine_readable_result,
)


def test_clean_import_run_is_ok() -> None:
    report = build_import_run_report(
        provider="canonical",
        mode="WRITE",
        feed_file="feed.json",
        read=100,
        new=5,
        updated=10,
        unchanged=85,
        unmatched=0,
        invalid=0,
        deactivated=0,
        run_id="clean-run",
    )

    status = evaluate_import_run(report)

    assert status.status == "ok"
    assert status.exit_code == 0
    assert status.reasons == []


def test_import_run_requiring_attention_is_review() -> None:
    report = build_import_run_report(
        provider="canonical",
        mode="WRITE",
        feed_file="feed.json",
        read=100,
        new=5,
        updated=10,
        unchanged=80,
        unmatched=3,
        invalid=1,
        deactivated=1,
        run_id="review-run",
    )

    status = evaluate_import_run(report)
    payload = machine_readable_result(report)

    assert status.status == "review"
    assert status.exit_code == 10
    assert status.reasons == [
        "unmatched_rows",
        "invalid_rows",
        "offers_deactivated",
    ]

    assert payload["status"] == "review"
    assert payload["exit_code"] == 10
    assert payload["run"]["run_id"] == "review-run"
