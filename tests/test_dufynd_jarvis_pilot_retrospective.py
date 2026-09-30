from __future__ import annotations

from scripts.report_dufynd_jarvis_pilot_retrospective import (
    build_pilot_retrospective,
    render_markdown,
)


class FakeBridge:
    def __init__(self):
        self.budget_status = {
            "budget_id": "jarvis_activation_pilot_001",
            "status": "active",
            "can_run": True,
            "cap_usd": 2.5,
            "max_runs": 20,
            "runs": 4,
            "spent_usd": 0.46,
            "remaining_usd": 2.04,
            "remaining_runs": 16,
        }
        self.budget_window = {
            "budget_id": "jarvis_activation_pilot_001",
            "status": "active",
            "model": "claude-sonnet-5",
            "cap_usd": 2.5,
            "max_runs": 20,
            "approved_decision_id": "decision_budget_001",
            "started_at": "2026-09-29T20:00:00+00:00",
        }
        self.approval = {
            "decision_id": "decision_budget_001",
            "status": "approved",
            "decision": {
                "approved": True,
                "cap_usd": 2.5,
                "max_runs": 20,
                "per_run_cap_usd": 0.25,
            },
        }
        self.runs = [
            {
                "id": "affiliate-1",
                "agent_name": "jarvis",
                "run_type": "inbox:affiliate_partner_changed",
                "created_at": "2026-09-29T20:01:00+00:00",
                "decisions": [
                    {
                        "budget_id": "jarvis_activation_pilot_001",
                        "cost_usd": 0.1,
                        "runtime": "dufynd_jarvis_v0_1",
                    }
                ],
            },
            {
                "id": "affiliate-2",
                "agent_name": "jarvis",
                "run_type": "inbox:affiliate_partner_changed",
                "created_at": "2026-09-29T20:02:00+00:00",
                "decisions": [
                    {
                        "budget_id": "jarvis_activation_pilot_001",
                        "cost_usd": 0.11,
                        "runtime": "dufynd_jarvis_v0_1",
                    }
                ],
            },
            {
                "id": "affiliate-3",
                "agent_name": "jarvis",
                "run_type": "inbox:affiliate_partner_changed",
                "created_at": "2026-09-29T20:03:00+00:00",
                "decisions": [
                    {
                        "budget_id": "jarvis_activation_pilot_001",
                        "cost_usd": 0.12,
                        "runtime": "dufynd_jarvis_v0_1",
                    }
                ],
            },
            {
                "id": "reference-1",
                "agent_name": "jarvis",
                "run_type": "inbox:creative_reference_added",
                "created_at": "2026-09-29T20:04:00+00:00",
                "decisions": [
                    {
                        "budget_id": "jarvis_activation_pilot_001",
                        "cost_usd": 0.13,
                        "runtime": "dufynd_jarvis_safe_worker_v1",
                    }
                ],
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


def test_retrospective_reports_clean_reconciled_pilot() -> None:
    report = build_pilot_retrospective(FakeBridge())

    assert report["checkpoint"] == "within_controls"
    assert report["controls"] == {
        "human_approval_valid": True,
        "run_count_reconciled": True,
        "spend_reconciled": True,
        "source_consistent": True,
        "controls_ok": True,
    }
    assert report["pilot"]["runs"] == 4
    assert report["pilot"]["spent_usd"] == 0.46
    assert report["pilot"]["average_run_usd"] == 0.115
    assert report["pilot"]["failed_runs"] == 0
    assert report["pilot"]["failed_model_turns"] == 0
    assert report["pilot"]["failed_model_turn_runs"] == 0
    assert report["pilot"]["historical_attention"] is False
    assert report["attention_codes"] == []


def test_retrospective_carries_budget_ledger_attention() -> None:
    bridge = FakeBridge()
    bridge.runs[-1]["run_type"] = "safe_task_failed:repo_current_commerce"
    bridge.runs[-1]["decisions"][0]["cost_usd"] = 0.25
    bridge.budget_status["spent_usd"] = 0.58

    report = build_pilot_retrospective(bridge)

    assert report["checkpoint"] == "attention"
    assert report["pilot"]["failed_runs"] == 1
    assert report["pilot"]["failed_spend_usd"] == 0.25
    assert report["pilot"]["historical_attention"] is True
    assert "failed_run_spend_present" in report["attention_codes"]
    assert "near_per_run_cap_activity" in report["attention_codes"]


def test_retrospective_marks_invalid_human_approval() -> None:
    bridge = FakeBridge()
    bridge.approval = {
        **bridge.approval,
        "status": "pending",
        "decision": {
            **bridge.approval["decision"],
            "approved": False,
        },
    }

    report = build_pilot_retrospective(bridge)

    assert report["checkpoint"] == "attention"
    assert report["controls"]["human_approval_valid"] is False
    assert report["controls"]["controls_ok"] is False
    assert "budget_approval_not_approved" in report["attention_codes"]


def test_retrospective_flags_source_drift_between_double_reads() -> None:
    bridge = FakeBridge()
    original_load = bridge.load_agent_runs_since
    calls = {"count": 0}

    def changing_runs(since_iso):
        calls["count"] += 1
        rows = list(original_load(since_iso))
        if calls["count"] >= 2:
            rows = rows + [
                {
                    "id": "late-run",
                    "agent_name": "jarvis",
                    "run_type": "event",
                    "created_at": "2026-09-29T20:05:00+00:00",
                    "decisions": [
                        {
                            "budget_id": "jarvis_activation_pilot_001",
                            "cost_usd": 0.01,
                        }
                    ],
                }
            ]
        return rows

    bridge.load_agent_runs_since = changing_runs

    report = build_pilot_retrospective(bridge)

    assert report["checkpoint"] == "attention"
    assert report["controls"]["source_consistent"] is False
    assert report["controls"]["controls_ok"] is False
    assert "retrospective_source_drift" in report["attention_codes"]


def test_retrospective_includes_runtime_cost_attribution() -> None:
    report = build_pilot_retrospective(FakeBridge())

    assert report["runtimes"] == [
        {
            "runtime": "dufynd_jarvis_v0_1",
            "runs": 3,
            "spent_usd": 0.33,
            "spend_share": 0.717391,
            "average_run_usd": 0.11,
            "max_run_usd": 0.12,
            "failed_model_turns": 0,
        },
        {
            "runtime": "dufynd_jarvis_safe_worker_v1",
            "runs": 1,
            "spent_usd": 0.13,
            "spend_share": 0.282609,
            "average_run_usd": 0.13,
            "max_run_usd": 0.13,
            "failed_model_turns": 0,
        },
    ]


def test_retrospective_includes_repeated_cost_centers() -> None:
    report = build_pilot_retrospective(FakeBridge())

    assert report["cost_centers"] == [
        {
            "family": "inbox:affiliate_partner_changed",
            "runs": 3,
            "spent_usd": 0.33,
            "spend_share": 0.717391,
            "average_run_usd": 0.11,
            "max_run_usd": 0.12,
        }
    ]


def test_markdown_renderer_is_operator_readable() -> None:
    report = build_pilot_retrospective(FakeBridge())

    markdown = render_markdown(report)

    assert "# DUFYND Jarvis Pilot Retrospective" in markdown
    assert "Checkpoint: **within_controls**" in markdown
    assert "Human approval valid: yes" in markdown
    assert "Spend: USD 0.460000" in markdown
    assert "## Runtime cost attribution" in markdown
    assert "dufynd_jarvis_v0_1: 3 runs, USD 0.330000" in markdown
    assert "dufynd_jarvis_safe_worker_v1: 1 runs, USD 0.130000" in markdown
    assert "Failed model turns: 0" in markdown
    assert "Maximum additional spend under current controls" in markdown
    assert "inbox:affiliate_partner_changed" in markdown
    assert "_Read-only retrospective." in markdown
