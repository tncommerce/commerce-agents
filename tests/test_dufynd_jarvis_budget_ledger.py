from __future__ import annotations

from scripts.report_dufynd_jarvis_budget_ledger import build_budget_ledger


class FakeBridge:
    def __init__(
        self,
        *,
        budget_status=None,
        budget_window=None,
        approval=None,
        runs=None,
    ):
        self.budget_status = budget_status or {
            "budget_id": "jarvis_activation_pilot_001",
            "status": "active",
            "can_run": True,
            "cap_usd": 2.5,
            "max_runs": 20,
            "runs": 2,
            "spent_usd": 0.3,
            "remaining_usd": 2.2,
            "remaining_runs": 18,
        }
        self.budget_window = budget_window or {
            "budget_id": "jarvis_activation_pilot_001",
            "status": "active",
            "model": "claude-sonnet-5",
            "cap_usd": 2.5,
            "max_runs": 20,
            "approved_decision_id": "decision_budget_001",
            "started_at": "2026-09-29T20:00:00+00:00",
        }
        self.approval = approval or {
            "decision_id": "decision_budget_001",
            "status": "approved",
            "decision": {
                "approved": True,
                "cap_usd": 2.5,
                "max_runs": 20,
                "per_run_cap_usd": 0.25,
            },
        }
        self.runs = runs or [
            {
                "id": "run-1",
                "agent_name": "jarvis",
                "run_type": "event",
                "created_at": "2026-09-29T20:05:00+00:00",
                "decisions": [
                    {
                        "budget_id": "jarvis_activation_pilot_001",
                        "cost_usd": 0.1,
                        "runtime": "dufynd_jarvis_v0_1",
                    }
                ],
            },
            {
                "id": "run-2",
                "agent_name": "jarvis",
                "run_type": "safe_task",
                "created_at": "2026-09-29T20:10:00+00:00",
                "decisions": [
                    {
                        "budget_id": "jarvis_activation_pilot_001",
                        "cost_usd": 0.2,
                        "runtime": "dufynd_jarvis_safe_worker_v1",
                        "worker_role": "commerce",
                        "failed_model_turn": True,
                    }
                ],
            },
            {
                "id": "other-budget",
                "agent_name": "jarvis",
                "run_type": "other",
                "created_at": "2026-09-29T20:15:00+00:00",
                "decisions": [{"budget_id": "different_budget", "cost_usd": 1.0}],
            },
        ]

    def load_budget_status(self, _budget_id):
        return self.budget_status

    def load_budget_window(self, _budget_id):
        return self.budget_window

    def load_human_decision(self, _decision_id):
        return self.approval

    def load_agent_runs_since(self, _since_iso):
        return self.runs


def test_budget_ledger_reconciles_audited_runs() -> None:
    report = build_budget_ledger(FakeBridge())

    assert report["status"] == "ok"
    assert report["ledger"]["runs"] == 2
    assert report["ledger"]["spent_usd"] == 0.3
    assert report["ledger"]["max_single_run_usd"] == 0.2
    assert report["ledger"]["average_run_usd"] == 0.15
    assert report["ledger"]["over_cap_runs"] == []
    assert report["ledger"]["by_run_type"]["event"] == {
        "runs": 1,
        "spent_usd": 0.1,
        "max_single_run_usd": 0.1,
        "average_run_usd": 0.1,
    }
    assert report["ledger"]["by_run_type"]["safe_task"] == {
        "runs": 1,
        "spent_usd": 0.2,
        "max_single_run_usd": 0.2,
        "average_run_usd": 0.2,
    }
    assert report["ledger"]["by_runtime"]["dufynd_jarvis_v0_1"] == {
        "runs": 1,
        "spent_usd": 0.1,
        "max_single_run_usd": 0.1,
        "failed_model_turns": 0,
        "average_run_usd": 0.1,
    }
    assert report["ledger"]["by_runtime"]["dufynd_jarvis_safe_worker_v1"] == {
        "runs": 1,
        "spent_usd": 0.2,
        "max_single_run_usd": 0.2,
        "failed_model_turns": 1,
        "average_run_usd": 0.2,
    }
    assert report["ledger"]["rows"][0]["runtime"] == "dufynd_jarvis_v0_1"
    assert report["ledger"]["rows"][0]["worker_role"] is None
    assert report["ledger"]["rows"][1]["runtime"] == "dufynd_jarvis_safe_worker_v1"
    assert report["ledger"]["rows"][1]["worker_role"] == "commerce"
    assert report["ledger"]["rows"][1]["failed_model_turns"] == 1
    assert report["approval"]["valid"] is True
    assert report["approval"]["cap_usd"] == 2.5
    assert report["approval"]["max_runs"] == 20
    assert report["approval"]["per_run_cap_usd"] == 0.25
    assert report["reconciliation"] == {
        "run_count_matches": True,
        "spend_matches": True,
    }
    assert report["remaining"]["run_cap_ceiling_usd"] == 4.5
    assert report["remaining"]["max_future_spend_usd"] == 2.2
    assert report["issues"] == []


def test_budget_ledger_future_spend_is_bounded_by_total_budget_headroom() -> None:
    bridge = FakeBridge(
        budget_status={
            "budget_id": "jarvis_activation_pilot_001",
            "status": "active",
            "can_run": True,
            "cap_usd": 2.5,
            "max_runs": 20,
            "runs": 16,
            "spent_usd": 1.8161,
            "remaining_usd": 0.6839,
            "remaining_runs": 4,
        },
        runs=[
            {
                "id": f"run-{index}",
                "agent_name": "jarvis",
                "run_type": "event",
                "created_at": "2026-09-29T20:05:00+00:00",
                "decisions": [
                    {
                        "budget_id": "jarvis_activation_pilot_001",
                        "cost_usd": 0.11350625,
                    }
                ],
            }
            for index in range(16)
        ],
    )

    report = build_budget_ledger(bridge)

    assert report["remaining"]["run_cap_ceiling_usd"] == 1.0
    assert report["remaining"]["max_future_spend_usd"] == 0.6839


def test_budget_ledger_flags_historical_per_run_cap_breach() -> None:
    bridge = FakeBridge(
        budget_status={
            "budget_id": "jarvis_activation_pilot_001",
            "status": "active",
            "can_run": True,
            "cap_usd": 2.5,
            "max_runs": 20,
            "runs": 1,
            "spent_usd": 0.2546842,
            "remaining_usd": 2.2453158,
            "remaining_runs": 19,
        },
        runs=[
            {
                "id": "run-over-cap",
                "agent_name": "jarvis",
                "run_type": "safe_task_failed:repo_current_commerce",
                "created_at": "2026-09-29T21:55:55+00:00",
                "decisions": [
                    {
                        "budget_id": "jarvis_activation_pilot_001",
                        "cost_usd": 0.2546842,
                    }
                ],
            }
        ],
    )

    report = build_budget_ledger(bridge)

    assert report["status"] == "attention"
    assert report["ledger"]["max_single_run_usd"] == 0.254684
    assert report["ledger"]["over_cap_runs"][0]["id"] == "run-over-cap"
    issue = next(
        item for item in report["issues"] if item["code"] == "historical_per_run_cap_exceeded"
    )
    assert issue["run_ids"] == ["run-over-cap"]


def test_budget_ledger_accepts_budget_status_display_rounding() -> None:
    bridge = FakeBridge(
        budget_status={
            "budget_id": "jarvis_activation_pilot_001",
            "status": "active",
            "can_run": True,
            "cap_usd": 2.5,
            "max_runs": 20,
            "runs": 2,
            "spent_usd": 0.3001,
            "remaining_usd": 2.1999,
            "remaining_runs": 18,
        },
        runs=[
            {
                "id": "run-1",
                "agent_name": "jarvis",
                "run_type": "event",
                "created_at": "2026-09-29T20:05:00+00:00",
                "decisions": [
                    {
                        "budget_id": "jarvis_activation_pilot_001",
                        "cost_usd": 0.10003,
                    }
                ],
            },
            {
                "id": "run-2",
                "agent_name": "jarvis",
                "run_type": "event",
                "created_at": "2026-09-29T20:10:00+00:00",
                "decisions": [
                    {
                        "budget_id": "jarvis_activation_pilot_001",
                        "cost_usd": 0.20003,
                    }
                ],
            },
        ],
    )

    report = build_budget_ledger(bridge)

    assert report["ledger"]["spent_usd"] == 0.30006
    assert report["reconciliation"]["spend_matches"] is True
    assert "budget_spend_reconciliation_mismatch" not in {item["code"] for item in report["issues"]}


def test_budget_ledger_flags_spend_and_run_count_mismatch() -> None:
    bridge = FakeBridge(
        budget_status={
            "budget_id": "jarvis_activation_pilot_001",
            "status": "active",
            "can_run": True,
            "cap_usd": 2.5,
            "max_runs": 20,
            "runs": 3,
            "spent_usd": 0.35,
            "remaining_usd": 2.15,
            "remaining_runs": 17,
        }
    )

    report = build_budget_ledger(bridge)

    codes = {item["code"] for item in report["issues"]}
    assert "budget_spend_reconciliation_mismatch" in codes
    assert "budget_run_count_reconciliation_mismatch" in codes
    assert report["reconciliation"]["spend_matches"] is False
    assert report["reconciliation"]["run_count_matches"] is False


def test_budget_ledger_requires_resolvable_human_approval() -> None:
    bridge = FakeBridge()
    bridge.approval = None
    bridge.load_human_decision = lambda _decision_id: None

    report = build_budget_ledger(bridge)

    assert report["status"] == "attention"
    assert "budget_approval_missing" in {item["code"] for item in report["issues"]}


def test_budget_ledger_rejects_nonapproved_human_decision() -> None:
    bridge = FakeBridge(
        approval={
            "decision_id": "decision_budget_001",
            "status": "pending",
            "decision": {
                "approved": False,
                "cap_usd": 2.5,
                "max_runs": 20,
                "per_run_cap_usd": 0.25,
            },
        }
    )

    report = build_budget_ledger(bridge)

    assert report["approval"]["valid"] is False
    assert "budget_approval_not_approved" in {item["code"] for item in report["issues"]}


def test_budget_ledger_flags_window_above_human_approval() -> None:
    bridge = FakeBridge(
        budget_window={
            "budget_id": "jarvis_activation_pilot_001",
            "status": "active",
            "model": "claude-sonnet-5",
            "cap_usd": 3.0,
            "max_runs": 25,
            "approved_decision_id": "decision_budget_001",
            "started_at": "2026-09-29T20:00:00+00:00",
        }
    )

    report = build_budget_ledger(bridge)

    issue = next(
        item for item in report["issues"] if item["code"] == "budget_window_exceeds_human_approval"
    )
    assert issue["window_cap_usd"] == 3.0
    assert issue["approved_cap_usd"] == 2.5
    assert issue["window_max_runs"] == 25
    assert issue["approved_max_runs"] == 20


def test_budget_ledger_requires_per_run_cap_in_human_approval() -> None:
    bridge = FakeBridge(
        approval={
            "decision_id": "decision_budget_001",
            "status": "approved",
            "decision": {
                "approved": True,
                "cap_usd": 2.5,
                "max_runs": 20,
            },
        }
    )

    report = build_budget_ledger(bridge)

    assert report["status"] == "attention"
    assert "per_run_approval_missing" in {item["code"] for item in report["issues"]}
