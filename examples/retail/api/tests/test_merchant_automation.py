from retail.api.merchant_automation import decide_automation
from retail.api.merchant_run_reports import build_import_run_report
from retail.api.merchant_run_status import machine_readable_result


def test_clean_machine_result_allows_automation() -> None:
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
        run_id="run-ok",
    )

    payload = machine_readable_result(report)
    decision = decide_automation(payload)

    assert decision.action == "continue"
    assert decision.exit_code == 0
    assert decision.reasons == []
    assert decision.run_id == "run-ok"


def test_review_or_invalid_result_holds_automation() -> None:
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
        run_id="run-review",
    )

    review_payload = machine_readable_result(report)
    review_decision = decide_automation(review_payload)

    assert review_decision.action == "hold"
    assert review_decision.exit_code == 10
    assert "unmatched_rows" in review_decision.reasons
    assert review_decision.run_id == "run-review"

    invalid_decision = decide_automation(
        {
            "status": "ok",
            "exit_code": 10,
            "reasons": [],
            "run": report.model_dump(mode="json"),
        }
    )

    assert invalid_decision.action == "hold"
    assert invalid_decision.exit_code == 20
    assert invalid_decision.reasons == ["inconsistent_machine_result"]
