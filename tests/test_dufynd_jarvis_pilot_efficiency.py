from __future__ import annotations

from scripts.report_dufynd_jarvis_pilot_efficiency import (
    build_pilot_efficiency_report,
)


class FakeBridge:
    def __init__(self):
        self.budget_status = {
            "budget_id": "jarvis_activation_pilot_001",
            "status": "active",
            "can_run": True,
            "cap_usd": 2.5,
            "max_runs": 20,
            "runs": 5,
            "spent_usd": 0.63,
            "remaining_usd": 1.87,
            "remaining_runs": 15,
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
                        "cost_usd": 0.10,
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
                        "cost_usd": 0.09,
                    }
                ],
            },
            {
                "id": "failed-1",
                "agent_name": "jarvis",
                "run_type": "safe_task_failed:repo_current_commerce",
                "created_at": "2026-09-29T20:05:00+00:00",
                "decisions": [
                    {
                        "budget_id": "jarvis_activation_pilot_001",
                        "cost_usd": 0.21,
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


def test_efficiency_report_surfaces_failed_and_near_cap_spend() -> None:
    report = build_pilot_efficiency_report(FakeBridge())

    assert report["status"] == "attention"
    assert report["totals"] == {
        "runs": 5,
        "spent_usd": 0.63,
        "average_run_usd": 0.126,
        "failed_runs": 1,
        "failed_spend_usd": 0.21,
        "failed_spend_share": 0.333333,
    }
    assert report["near_cap"]["threshold_usd"] == 0.2
    assert report["near_cap"]["runs"] == [
        {
            "id": "failed-1",
            "run_type": "safe_task_failed:repo_current_commerce",
            "cost_usd": 0.21,
        }
    ]


def test_efficiency_report_groups_repeated_cost_centers() -> None:
    report = build_pilot_efficiency_report(FakeBridge())

    affiliate = report["families"][0]
    assert affiliate == {
        "family": "inbox:affiliate_partner_changed",
        "runs": 3,
        "spent_usd": 0.33,
        "spend_share": 0.52381,
        "average_run_usd": 0.11,
        "max_run_usd": 0.12,
    }
    assert report["repeated_cost_centers"] == [affiliate]
    signal = next(item for item in report["signals"] if item["code"] == "repeated_cost_centers")
    assert signal["families"] == ["inbox:affiliate_partner_changed"]


def test_efficiency_report_observed_capacity_is_descriptive_and_bounded() -> None:
    report = build_pilot_efficiency_report(FakeBridge())

    assert report["remaining"]["usd"] == 1.87
    assert report["remaining"]["runs"] == 15
    assert report["remaining"]["max_future_spend_usd"] == 1.87
    assert report["remaining"]["observed_average_run_capacity"] == 14
    assert "descriptive only" in report["remaining"]["capacity_note"]


def test_efficiency_report_can_be_clean_without_failures_or_near_cap_runs() -> None:
    bridge = FakeBridge()
    bridge.budget_status = {
        **bridge.budget_status,
        "runs": 3,
        "spent_usd": 0.3,
        "remaining_usd": 2.2,
        "remaining_runs": 17,
    }
    bridge.runs = bridge.runs[:3]

    report = build_pilot_efficiency_report(bridge)

    assert report["status"] == "ok"
    assert report["totals"]["failed_runs"] == 0
    assert report["near_cap"]["runs"] == []
    assert all(signal["severity"] != "attention" for signal in report["signals"])


def test_run_family_collapses_task_specific_failure_suffixes() -> None:
    bridge = FakeBridge()
    bridge.budget_status = {
        **bridge.budget_status,
        "runs": 2,
        "spent_usd": 0.2,
        "remaining_usd": 2.3,
        "remaining_runs": 18,
    }
    bridge.runs = [
        {
            "id": "failed-a",
            "agent_name": "jarvis",
            "run_type": "safe_task_failed:commerce-a",
            "created_at": "2026-09-29T20:01:00+00:00",
            "decisions": [
                {
                    "budget_id": "jarvis_activation_pilot_001",
                    "cost_usd": 0.1,
                }
            ],
        },
        {
            "id": "failed-b",
            "agent_name": "jarvis",
            "run_type": "safe_task_failed:commerce-b",
            "created_at": "2026-09-29T20:02:00+00:00",
            "decisions": [
                {
                    "budget_id": "jarvis_activation_pilot_001",
                    "cost_usd": 0.1,
                }
            ],
        },
    ]

    report = build_pilot_efficiency_report(bridge)

    assert report["families"] == [
        {
            "family": "safe_task_failed",
            "runs": 2,
            "spent_usd": 0.2,
            "spend_share": 1.0,
            "average_run_usd": 0.1,
            "max_run_usd": 0.1,
        }
    ]
