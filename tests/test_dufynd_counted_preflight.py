from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta

import pytest
import scripts.dufynd_counted_nightshift as counted
import scripts.dufynd_jarvis_nightshift as nightshift
from scripts.dufynd_anthropic_counted import canonical
from scripts.dufynd_bounded_provider import BudgetGate


class ReadOnlyBridge:
    def __init__(self, contract):
        self.calls = []
        self.writes = []
        self.resolver = {"allowed": False, "reason": "no_usable_approved_budget"}
        self.state = {
            "provider_contract": {
                "model": contract["model"],
                "enabled": True,
                "dry_run": False,
                "expires_at": contract["expires_at"],
                "evidence": {"pricing_digest": hashlib.sha256(canonical(contract)).hexdigest()},
            },
            "functions": [
                "resolve_dufynd_nightshift_budget",
                "reserve_dufynd_model_call",
                "dispatch_dufynd_counted_call",
                "settle_dufynd_counted_call",
                "reconcile_dufynd_budget_reservations",
            ],
            "leases": {"active_workers": [], "tech": {"status": "released"}},
            "observer_health": [{"observer_id": "observer", "health_status": "healthy"}],
            "historical_pilot_budget": {
                "budget_id": "jarvis_activation_pilot_001",
                "spent_usd": 2.5046854,
                "runs": 19,
            },
            "reservation_snapshot": {"existing_total": 0, "existing_dispatched": 0},
        }
        self.session = {
            "session_id": "historical",
            "started_at": "2026-10-01T21:44:14+00:00",
            "ended_at": "2026-10-01T21:47:25+00:00",
            "task_results": [],
        }
        self.supervisor = {"supervisor_id": "stale", "started_at": "2026-10-01T21:44:00+00:00"}

    def _rpc(self, name, payload):
        self.calls.append(name)
        assert name in {"get_dufynd_counted_preflight_state", "resolve_dufynd_nightshift_budget"}
        return copy.deepcopy(
            self.state if name == "get_dufynd_counted_preflight_state" else self.resolver
        )

    def load_autonomy_queue(self):
        return {"safe_to_execute": [{"task_id": "safe", "domain": "research"}], "in_progress": []}

    def load_master_status_entry(self, key):
        # A preflight must never read persisted worker/supervisor state.
        return {"value": self.session if key == nightshift.SESSION_KEY else self.supervisor}

    def load_agent_runs_since(self, started):
        return [{"created_at": "2026-10-04T00:00:30+00:00", "decisions": [{"cost_usd": 99}]}]

    def load_health(self):
        return {"inbox": {}}

    def load_pending_decisions(self):
        return []

    def load_budget_status(self, budget_id):
        raise AssertionError("No implicit pilot budget lookup")

    def upsert_master_status(self, **kwargs):
        assert kwargs["key"] == "jarvis.counted_nightshift.terminal"
        self.writes.append(kwargs)


@pytest.fixture
def setup(monkeypatch):
    contract = {
        "model": "claude-sonnet-5",
        "provider": "anthropic",
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    bridge = ReadOnlyBridge(contract)
    monkeypatch.setattr(counted, "pricing", lambda: contract)
    monkeypatch.setattr(counted, "DufyndJarvisBridge", lambda: bridge)
    monkeypatch.setenv("DUFYND_JARVIS_PROVIDER_PATH", "")
    monkeypatch.setenv("GITHUB_RUN_ID", "new-run")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("GITHUB_SHA", "current-head")
    monkeypatch.setenv("DUFYND_JARVIS_BUDGET_ID", "jarvis_activation_pilot_001")
    return bridge


def test_preflight_no_budget_is_success_and_does_not_inherit_history(setup, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["counted", "--preflight"])
    monkeypatch.setattr(counted, "run_nightshift", lambda **kw: pytest.fail("Worker started"))
    monkeypatch.setattr(
        counted, "write_morning_report", lambda *a, **kw: pytest.fail("Historical report loaded")
    )
    monkeypatch.setattr(
        setup, "load_master_status_entry", lambda *a: pytest.fail("Historical session loaded")
    )
    monkeypatch.setattr(
        setup, "load_agent_runs_since", lambda *a: pytest.fail("Historical costs loaded")
    )
    assert counted.main() == 0
    path = tmp_path / "jarvis-nightshift-report"
    report = json.loads((path / "preflight-report.json").read_text())
    terminal = json.loads((path / "counted-terminal.json").read_text())
    assert report["run_type"] == "nightshift_bounded_preflight"
    assert report["github_run_id"] == "new-run" and report["head_sha"] == "current-head"
    assert report["budget_gate"]["status"] == "BLOCKED_AS_EXPECTED"
    assert report["budget_gate"]["reason"] == "no_usable_approved_budget"
    assert report["current_budget"] is None and report["budget_id"] is None
    assert report["worker_session_started"] is False
    assert report["paid_requests"] == report["reservations_created"] == report["new_spend_usd"] == 0
    assert report["current_preflight_cost_usd"] == 0
    assert report["historical_context"]["pilot_budget"]["spent_usd"] == 2.5046854
    assert "session_id" not in report and "current_runs" not in report
    assert terminal["budget_id"] is None and terminal["worker_session_started"] is False
    assert (path / "preflight-report.md").exists() and not (path / "morning-report.json").exists()
    assert len(setup.writes) == 1
    assert setup.calls == ["get_dufynd_counted_preflight_state", "resolve_dufynd_nightshift_budget"]


@pytest.mark.parametrize(
    "reason", ["ambiguous_active_budgets", "provider_contract_unverified_or_expired"]
)
def test_other_budget_errors_remain_fail_closed(setup, reason):
    setup.resolver["reason"] = reason
    with pytest.raises(BudgetGate, match=reason):
        counted.build_preflight_report(setup, started_at=datetime.now(UTC))


def test_missing_safety_function_is_technical_failure(setup):
    setup.state["functions"].remove("settle_dufynd_counted_call")
    with pytest.raises(BudgetGate, match="functions_missing"):
        counted.build_preflight_report(setup, started_at=datetime.now(UTC))


def test_expired_live_contract_is_failure(setup):
    setup.state["provider_contract"]["expires_at"] = "2020-01-01T00:00:00+00:00"
    with pytest.raises(BudgetGate, match="unverified_or_expired"):
        counted.build_preflight_report(setup, started_at=datetime.now(UTC))


def test_paid_start_without_budget_remains_blocked(setup, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["counted", "--approval-token", "GO-JARVIS-NIGHTSHIFT"])
    monkeypatch.setattr(
        counted,
        "resolve_budget",
        lambda b: (_ for _ in ()).throw(BudgetGate("no_usable_approved_budget")),
    )
    monkeypatch.setattr(counted, "run_nightshift", lambda **kw: pytest.fail("Worker started"))
    assert counted.main() == 2
    terminal = json.loads((tmp_path / "jarvis-nightshift-report/counted-terminal.json").read_text())
    assert terminal["worker_session_started"] is False and terminal["budget_id"] is None
    assert not (tmp_path / "jarvis-nightshift-report/morning-report.json").exists()


def test_paid_start_binds_runtime_model_to_verified_contract(setup, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["counted", "--approval-token", "GO-JARVIS-NIGHTSHIFT", "--max-tasks", "3"],
    )
    monkeypatch.setenv("GITHUB_REF", "refs/heads/scentai-mvp")
    monkeypatch.setenv("DUFYND_JARVIS_ACTIVE", "1")
    monkeypatch.setenv("DUFYND_JARVIS_AUTONOMOUS", "1")
    monkeypatch.delenv("DUFYND_JARVIS_MODEL", raising=False)
    monkeypatch.setattr(
        counted,
        "resolve_budget",
        lambda bridge: (
            "jarvis_nightshift_canary_test",
            {"allowed": True, "budget": {"budget_id": "jarvis_nightshift_canary_test"}},
        ),
    )

    async def fake_run_nightshift(bridge, **kwargs):
        assert os.getenv("DUFYND_JARVIS_MODEL") == "claude-sonnet-5"
        assert kwargs["max_tasks"] == 3
        return {
            "session_id": "current",
            "started_at": "2026-10-04T00:00:00+00:00",
            "ended_at": "2026-10-04T00:01:00+00:00",
            "status": "completed",
            "stop_reason": "no_safe_work",
            "task_results": [],
        }

    monkeypatch.setattr(counted, "run_nightshift", fake_run_nightshift)
    monkeypatch.setattr(counted, "write_morning_report", lambda *args, **kwargs: {})
    assert counted.main() == 0
    terminal = json.loads((tmp_path / "jarvis-nightshift-report/counted-terminal.json").read_text())
    assert terminal["budget_id"] == "jarvis_nightshift_canary_test"
    assert terminal["worker_session_started"] is True


def current_session():
    return {
        "session_id": "current",
        "github_run_id": "new-run",
        "github_run_attempt": "1",
        "head_sha": "current-head",
        "started_at": "2026-10-04T00:00:00+00:00",
        "ended_at": "2026-10-04T00:01:00+00:00",
        "status": "completed",
        "task_results": [],
    }


def test_morning_report_rejects_persisted_historical_session(setup):
    with pytest.raises(RuntimeError, match="No Jarvis nightshift"):
        nightshift.build_morning_report(setup, qa_status="success")


def test_current_session_ignores_stale_supervisor_and_foreign_costs(setup):
    setup.session = current_session()
    report, _ = nightshift.build_morning_report(setup, qa_status="success")
    assert report["session_id"] == "current" and report["supervisor"] is None
    assert report["budget"] is None and report["ai_cost_usd"] == 0
    assert report["ai_cost_complete"] is False
    assert report["head_sha"] == "current-head"


@pytest.mark.parametrize("field", ["github_run_id", "github_run_attempt", "head_sha"])
def test_morning_report_rejects_mismatched_provenance(setup, field):
    session = current_session()
    session[field] = "wrong"
    with pytest.raises(RuntimeError, match="provenance mismatch"):
        nightshift.build_morning_report(setup, qa_status="success", expected_session=session)


def test_returned_session_survives_persisted_key_overwrite(setup):
    report, _ = nightshift.build_morning_report(
        setup, qa_status="success", expected_session=current_session()
    )
    assert report["session_id"] == "current"


def test_matching_morning_report_cost_is_bound_to_execution(setup, monkeypatch):
    setup.session = current_session()
    monkeypatch.setattr(
        setup,
        "load_agent_runs_since",
        lambda *a: [
            {
                "created_at": "2026-10-04T00:00:30+00:00",
                "decisions": [
                    {
                        "cost_usd": 0.02,
                        "github_run_id": "new-run",
                        "github_run_attempt": "1",
                        "head_sha": "current-head",
                    },
                    {"cost_usd": 50, "github_run_id": "old-run", "head_sha": "old-head"},
                ],
            }
        ],
    )
    report, _ = nightshift.build_morning_report(setup, qa_status="success")
    assert report["ai_cost_usd"] == 0.02 and report["ai_cost_complete"] is False


def test_supervisor_rejects_foreign_session_summary(setup):
    setup.session = {}
    setup.supervisor = {
        **current_session(),
        "supervisor_id": "supervisor",
        "session_summaries": [{**current_session(), "github_run_id": "old-run"}],
    }
    with pytest.raises(RuntimeError, match="supervisor/session provenance"):
        nightshift.build_morning_report(setup, qa_status="success")


def test_report_requires_explicit_execution_outside_github(setup, monkeypatch):
    monkeypatch.delenv("GITHUB_RUN_ID")
    with pytest.raises(RuntimeError, match="identity required"):
        nightshift.build_morning_report(setup, qa_status="success")


def test_session_cannot_resume_across_runs(setup):
    setup.session = {
        **current_session(),
        "status": "running",
        "github_run_id": "old-run",
        "source_fingerprint_sha256": "same",
    }
    session = nightshift._load_or_start_session(
        setup, fingerprint="same", max_tasks=2, max_events=0
    )
    assert session["session_id"] != "current" and session["github_run_id"] == "new-run"
