import json
from types import SimpleNamespace

from retail.api import merchant_operational_runner as runner


def test_operational_runner_continues_clean_import(
    monkeypatch,
) -> None:
    payload = {
        "status": "ok",
        "exit_code": 0,
        "reasons": [],
        "run": {
            "run_id": "run-ok",
            "occurred_at": "2026-09-17T18:00:00Z",
            "provider": "canonical",
            "mode": "WRITE",
            "feed_file": "feed.json",
            "authoritative_merchant_id": None,
            "authoritative_data_source": None,
            "allow_empty_authoritative": False,
            "read": 10,
            "new": 1,
            "updated": 2,
            "unchanged": 7,
            "unmatched": 0,
            "invalid": 0,
            "deactivated": 0,
        },
    }

    captured_command = []

    def fake_run(command, **kwargs):
        captured_command.extend(command)
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

    monkeypatch.setattr(
        runner.subprocess,
        "run",
        fake_run,
    )

    result = runner.run_import_with_gate(["python", "-m", "retail.api.import_merchant_feed"])

    assert result.action == "continue"
    assert result.exit_code == 0
    assert result.run_id == "run-ok"
    assert "--machine-readable" in captured_command


def test_operational_runner_holds_review_and_bad_output(
    monkeypatch,
) -> None:
    review_payload = {
        "status": "review",
        "exit_code": 10,
        "reasons": ["unmatched_rows"],
        "run": {
            "run_id": "run-review",
            "occurred_at": "2026-09-17T18:00:00Z",
            "provider": "canonical",
            "mode": "WRITE",
            "feed_file": "feed.json",
            "authoritative_merchant_id": None,
            "authoritative_data_source": None,
            "allow_empty_authoritative": False,
            "read": 10,
            "new": 1,
            "updated": 2,
            "unchanged": 6,
            "unmatched": 1,
            "invalid": 0,
            "deactivated": 0,
        },
    }

    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=10,
            stdout=json.dumps(review_payload),
            stderr="",
        ),
    )

    review = runner.run_import_with_gate(["python", "-m", "retail.api.import_merchant_feed"])

    assert review.action == "hold"
    assert review.exit_code == 10
    assert review.reasons == ["unmatched_rows"]

    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout="not-json",
            stderr="boom",
        ),
    )

    invalid = runner.run_import_with_gate(["python", "-m", "retail.api.import_merchant_feed"])

    assert invalid.action == "hold"
    assert invalid.exit_code == 20
    assert invalid.reasons == ["invalid_import_output"]


def test_operational_runner_holds_on_process_exit_mismatch(
    monkeypatch,
) -> None:
    payload = {
        "status": "ok",
        "exit_code": 0,
        "reasons": [],
        "run": {
            "run_id": "run-mismatch",
            "occurred_at": "2026-09-17T18:00:00Z",
            "provider": "canonical",
            "mode": "WRITE",
            "feed_file": "feed.json",
            "authoritative_merchant_id": None,
            "authoritative_data_source": None,
            "allow_empty_authoritative": False,
            "read": 10,
            "new": 1,
            "updated": 2,
            "unchanged": 7,
            "unmatched": 0,
            "invalid": 0,
            "deactivated": 0,
        },
    }

    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout=json.dumps(payload),
            stderr="unexpected process failure",
        ),
    )

    result = runner.run_import_with_gate(["python", "-m", "retail.api.import_merchant_feed"])

    assert result.action == "hold"
    assert result.exit_code == 20
    assert result.import_exit_code == 1
    assert result.reasons == ["process_exit_mismatch"]
    assert result.run_id == "run-mismatch"
