from __future__ import annotations

from scripts.check_dufynd_jarvis_pilot_preflight import evaluate_pilot_preflight


def retrospective(**overrides):
    payload = {
        "budget_id": "jarvis_activation_pilot_001",
        "controls": {
            "human_approval_valid": True,
            "run_count_reconciled": True,
            "spend_reconciled": True,
            "source_consistent": True,
            "controls_ok": True,
        },
        "remaining": {
            "runs": 4,
            "usd": 0.6839,
            "max_future_spend_usd": 0.6839,
        },
        "attention_codes": [
            "historical_per_run_cap_exceeded",
            "failed_run_spend_present",
            "near_per_run_cap_activity",
        ],
    }
    payload.update(overrides)
    return payload


def test_historical_attention_is_warning_not_hard_blocker() -> None:
    report = evaluate_pilot_preflight(retrospective())

    assert report["ready"] is True
    assert report["blockers"] == []
    assert report["warnings"] == [
        "failed_run_spend_present",
        "historical_per_run_cap_exceeded",
        "near_per_run_cap_activity",
    ]
    assert report["remaining"]["runs"] == 4
    assert report["remaining"]["usd"] == 0.6839


def test_invalid_human_approval_blocks_preflight() -> None:
    payload = retrospective()
    payload["controls"] = {
        **payload["controls"],
        "human_approval_valid": False,
        "controls_ok": False,
    }
    payload["attention_codes"] = ["budget_approval_not_approved"]

    report = evaluate_pilot_preflight(payload)

    assert report["ready"] is False
    assert report["blockers"] == [
        "budget_approval_not_approved",
        "human_approval_invalid",
    ]


def test_reconciliation_and_source_drift_block_preflight() -> None:
    payload = retrospective()
    payload["controls"] = {
        "human_approval_valid": True,
        "run_count_reconciled": False,
        "spend_reconciled": False,
        "source_consistent": False,
        "controls_ok": False,
    }
    payload["attention_codes"] = [
        "budget_run_count_reconciliation_mismatch",
        "budget_spend_reconciliation_mismatch",
        "retrospective_source_drift",
    ]

    report = evaluate_pilot_preflight(payload)

    assert report["ready"] is False
    assert set(report["blockers"]) == {
        "run_count_not_reconciled",
        "spend_not_reconciled",
        "report_source_drift",
        "budget_run_count_reconciliation_mismatch",
        "budget_spend_reconciliation_mismatch",
        "retrospective_source_drift",
    }


def test_exhausted_run_limit_blocks_preflight() -> None:
    payload = retrospective(
        remaining={
            "runs": 0,
            "usd": 0.5,
            "max_future_spend_usd": 0.0,
        }
    )

    report = evaluate_pilot_preflight(payload)

    assert report["ready"] is False
    assert report["blockers"] == [
        "no_remaining_approved_budget",
        "no_remaining_approved_runs",
    ]


def test_exhausted_total_budget_blocks_preflight() -> None:
    payload = retrospective(
        remaining={
            "runs": 4,
            "usd": 0.0,
            "max_future_spend_usd": 0.0,
        }
    )

    report = evaluate_pilot_preflight(payload)

    assert report["ready"] is False
    assert report["blockers"] == ["no_remaining_approved_budget"]


def test_hard_attention_code_blocks_even_when_control_flags_are_true() -> None:
    payload = retrospective(
        attention_codes=["budget_window_exceeds_human_approval"]
    )

    report = evaluate_pilot_preflight(payload)

    assert report["ready"] is False
    assert report["blockers"] == ["budget_window_exceeds_human_approval"]
    assert report["warnings"] == []
