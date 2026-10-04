from decimal import Decimal

import pytest
from scripts.dufynd_counted_reporting import report_counted_costs
from scripts.dufynd_jarvis_nightshift import _audited_run_cost_known, _decision_cost


class Bridge:
    def load_budget_window(self, budget):
        return {"budget_id": budget, "provider": "anthropic", "model": "fake"}

    def load_budget_reservations(self, budget):
        return [
            {
                "budget_id": budget,
                "task_id": "audit",
                "reservation_id": "rid",
                "status": "settled",
                "reserved_usd": "0.036864",
                "actual_usd": "0.027142",
                "provider_receipt_id": "call",
                "created_at": "2026-10-04T00:00:01+00:00",
                "dispatched_at": "2026-10-04T00:00:02+00:00",
                "settled_at": "2026-10-04T00:00:03+00:00",
            }
        ]

    def load_budget_status(self, budget):
        return {"budget_id": budget, "remaining_usd": "0.122858", "remaining_runs": 2}


def test_settled_counted_cost_and_remaining_budget():
    result = report_counted_costs(
        Bridge(), "canary", "2026-10-04T00:00:00+00:00", "2026-10-04T00:01:00+00:00"
    )
    assert Decimal(result["actual_spend_usd"]) == Decimal("0.027142")
    assert result["remaining_budget_usd"] == "0.122858"
    assert Decimal(result["reserved_unsettled_usd"]) == 0
    assert result["calls"] == 1
    assert result["provider_cost_unknown"] is False
    assert result["ledger"][0]["provider_receipt_id"] == "call"


def test_pilot_budget_never_mixed():
    with pytest.raises(ValueError, match="counted_budget"):
        report_counted_costs(Bridge(), "jarvis_activation_pilot_001", "", "")


@pytest.mark.parametrize("invalid", [True, "NaN", "Infinity", "-1", "bad", None])
def test_invalid_cost_never_counted(invalid):
    assert _decision_cost({"cost_usd": invalid}) == 0


def test_decimal_text_is_recognized_as_audited_cost():
    assert _decision_cost({"cost_usd": "0.055622"}) == 0.055622
    assert _audited_run_cost_known({"decisions": [{"cost_usd": "0.055622"}]})


def test_morning_report_uses_counted_ledger_instead_of_zero_text_cost(monkeypatch):
    import scripts.dufynd_jarvis_nightshift as nightshift
    from tests.test_dufynd_jarvis_nightshift import FakeBridge

    class ReportBridge(FakeBridge, Bridge):
        def load_budget_status(self, budget):
            return Bridge.load_budget_status(self, budget)

    bridge = ReportBridge()
    bridge.master[nightshift.SESSION_KEY] = {
        "value": {
            "session_id": "counted",
            "status": "completed",
            "started_at": "2026-10-04T00:00:00+00:00",
            "ended_at": "2026-10-04T00:01:00+00:00",
            "stop_reason": "no_safe_work",
            "budget_id": "canary",
            "task_results": [{"task_id": "audit", "final_status": "blocked", "attempts": 1}],
        }
    }
    bridge.agent_runs_override = []
    monkeypatch.setenv("DUFYND_JARVIS_BUDGET_ID", "jarvis_activation_pilot_001")
    report, markdown = nightshift.build_morning_report(
        bridge, historical_report=True, qa_status="success"
    )
    assert report["ai_cost_usd"] == 0.027142
    assert report["ai_cost_source"] == "counted_reservations_and_settlements"
    assert report["counted_costs"]["remaining_budget_usd"] == "0.122858"
    assert report["counted_costs"]["reserved_unsettled_usd"] == "0"
    assert "0.027142" in markdown
    assert "jarvis_activation_pilot_001" not in markdown
