from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys

import pytest
import scripts.dufynd_jarvis_runtime as jarvis_runtime
from scripts.dufynd_jarvis_runtime import (
    SYSTEM_PROMPT,
    _bounded_autonomous_max_events,
    _bounded_supervisor_max_events,
    _deterministic_event_summary,
    _extract_safe_task_state,
    _require_active_runtime,
    _require_autonomous_session,
    _require_budget_window,
    _require_runtime_id,
    _sdk_budget_limit,
    allowed_tool_names,
    event_prompt,
    process_autonomous_cycle,
    process_branch_task,
    process_next,
    process_safe_task,
    runtime_readiness,
)


class EmptyBridge:
    def load_health(self):
        return {"inbox": {"pending": 0}}

    def claim_next_inbox_event(self):
        return None


class BudgetBridge:
    def __init__(
        self,
        can_run: bool = True,
        *,
        max_runs: int = 10,
        approved_max_runs: int = 10,
        cap_usd: float = 2.5,
        approved_cap_usd: float = 2.5,
        approved_per_run_cap_usd: float = 0.25,
    ):
        self.can_run = can_run
        self.max_runs = max_runs
        self.approved_max_runs = approved_max_runs
        self.cap_usd = cap_usd
        self.approved_cap_usd = approved_cap_usd
        self.approved_per_run_cap_usd = approved_per_run_cap_usd

    def load_budget_status(self, budget_id: str):
        return {
            "budget_id": budget_id,
            "status": "active" if self.can_run else "planned",
            "model": "claude-sonnet-5",
            "can_run": self.can_run,
        }

    def load_budget_window(self, budget_id: str):
        return {
            "budget_id": budget_id,
            "cap_usd": self.cap_usd,
            "max_runs": self.max_runs,
            "approved_decision_id": "decision_jarvis_active_runner_001",
        }

    def load_human_decision(self, decision_id: str):
        assert decision_id == "decision_jarvis_active_runner_001"
        return {
            "decision_id": decision_id,
            "status": "approved",
            "decision": {
                "approved": True,
                "cap_usd": self.approved_cap_usd,
                "max_runs": self.approved_max_runs,
                "per_run_cap_usd": self.approved_per_run_cap_usd,
            },
        }


class SupervisorBridge:
    def __init__(self, pending: int):
        self.pending = pending

    def load_health(self):
        return {"inbox": {"pending": self.pending}}


class SafeTaskBridge:
    def __init__(self, safe_tasks):
        self.safe_tasks = safe_tasks

    def load_autonomy_queue(self):
        return {"safe_to_execute": self.safe_tasks}


def test_runtime_has_only_internal_safe_tool_surface() -> None:
    names = allowed_tool_names()

    assert "mcp__dufynd_jarvis__load_creative_context" in names
    assert "mcp__dufynd_jarvis__load_creative_catalog" in names
    assert "mcp__dufynd_jarvis__record_lesson" in names
    assert "mcp__dufynd_jarvis__record_content_idea" in names
    assert "mcp__dufynd_jarvis__link_idea_pattern" in names
    assert all("publish" not in name for name in names)
    assert all("spend" not in name for name in names)
    assert all("merge" not in name for name in names)


def test_runtime_prompt_preserves_dufynd_and_human_gates() -> None:
    assert "DUFYND is the current public brand" in SYSTEM_PROMPT
    assert "SCENTAI is historical/legacy only" in SYSTEM_PROMPT
    assert "do not\npublish content" in SYSTEM_PROMPT
    assert "final decision-maker" in SYSTEM_PROMPT


def test_runtime_prompt_prefers_bounded_creative_catalog() -> None:
    assert "load the bounded creative catalog first" in SYSTEM_PROMPT
    assert "use the full creative context only when the bounded catalog is insufficient" in SYSTEM_PROMPT


def test_event_prompt_contains_structured_event() -> None:
    prompt = event_prompt(
        {
            "inbox_id": 12,
            "event_type": "creative_reference_added",
            "source_id": "example_99",
        }
    )

    assert "creative_reference_added" in prompt
    assert "example_99" in prompt
    assert '"inbox_id": 12' in prompt


def test_deterministic_affiliate_status_change_requires_no_model() -> None:
    summary = _deterministic_event_summary(
        {
            "event_type": "affiliate_partner_changed",
            "source_id": "merchant",
            "payload": {
                "merchant_name": "Merchant",
                "status_before": "applied",
                "status_after": "rejected",
                "feed_ready_before": False,
                "feed_ready_after": False,
                "tracking_ready_before": False,
                "tracking_ready_after": False,
            },
        }
    )

    assert summary is not None
    assert "no model reasoning is required" in summary


def test_affiliate_readiness_change_still_requires_model() -> None:
    summary = _deterministic_event_summary(
        {
            "event_type": "affiliate_partner_changed",
            "payload": {
                "status_before": "approved",
                "status_after": "tracking_ready",
                "feed_ready_before": False,
                "feed_ready_after": False,
                "tracking_ready_before": False,
                "tracking_ready_after": True,
            },
        }
    )

    assert summary is None


def test_process_next_is_noop_when_inbox_is_empty(capsys) -> None:
    result = asyncio.run(process_next(EmptyBridge()))

    assert result == 0
    assert "no pending event" in capsys.readouterr().out.lower()


def test_safe_worker_ignores_non_repo_current_tasks(capsys) -> None:
    result = asyncio.run(
        process_safe_task(
            SafeTaskBridge(
                [
                    {
                        "task_id": "legacy_safe_task",
                        "requires_human_approval": False,
                    }
                ]
            )
        )
    )

    assert result == 0
    assert "no repo-current safe task" in capsys.readouterr().out.lower()


def test_safe_worker_refuses_human_approval_task(capsys) -> None:
    result = asyncio.run(
        process_safe_task(
            SafeTaskBridge(
                [
                    {
                        "task_id": "repo_current_commerce",
                        "requires_human_approval": True,
                    }
                ]
            )
        )
    )

    assert result == 0
    assert "no repo-current safe task" in capsys.readouterr().out.lower()


def test_safe_worker_prompt_names_high_impact_boundaries() -> None:
    prompt = jarvis_runtime.safe_task_prompt(
        {
            "task_id": "repo_current_commerce",
            "instruction": "Research licensed image sources.",
        }
    )

    assert "Do not perform any high-impact action" in prompt
    assert "licensing rights" in prompt
    assert "DUFYND_TASK_STATE:" in prompt
    assert "waiting_human_input" in prompt
    assert "waiting_external" in prompt


def test_safe_worker_state_parser_accepts_machine_readable_outcome() -> None:
    assert (
        _extract_safe_task_state(
            "Evidence complete.\nDUFYND_TASK_STATE: waiting_external"
        )
        == "waiting_external"
    )
    assert _extract_safe_task_state("DUFYND_TASK_STATE: invalid") is None


def test_sdk_budget_limit_keeps_headroom_below_approved_cap() -> None:
    assert _sdk_budget_limit(0.25) == 0.2
    assert 0 < _sdk_budget_limit(0.05) < 0.05


def test_branch_worker_ignores_non_engineering_tasks(capsys) -> None:
    result = asyncio.run(
        process_branch_task(
            SafeTaskBridge(
                [
                    {
                        "task_id": "repo_current_commerce",
                        "domain": "commerce",
                        "requires_human_approval": False,
                    }
                ]
            )
        )
    )

    assert result == 0
    assert "no repo-current safe engineering task" in capsys.readouterr().out.lower()


def test_branch_worker_prompt_preserves_isolated_patch_boundary() -> None:
    prompt = jarvis_runtime.branch_task_prompt(
        {
            "task_id": "repo_current_engineering",
            "domain": "engineering",
            "instruction": "Fix one tested UI issue.",
        }
    )

    assert "Do not run commands yourself" in prompt
    assert "Do not mark the task complete" in prompt


def test_branch_worker_denies_shell_and_allows_edit_tools(monkeypatch) -> None:
    monkeypatch.setenv("DUFYND_JARVIS_ACTIVE", "1")
    monkeypatch.setenv("DUFYND_JARVIS_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret")
    monkeypatch.setenv("DUFYND_JARVIS_MAX_TURNS", "8")
    monkeypatch.setenv("DUFYND_JARVIS_MAX_BUDGET_USD", "0.25")

    options = jarvis_runtime.make_branch_worker_options(BudgetBridge())

    assert "Write" in options.allowed_tools
    assert "Edit" in options.allowed_tools
    assert "Bash" in options.disallowed_tools
    assert "WebSearch" in options.disallowed_tools


def test_safe_worker_options_reserve_budget_headroom(monkeypatch) -> None:
    monkeypatch.setenv("DUFYND_JARVIS_ACTIVE", "1")
    monkeypatch.setenv("DUFYND_JARVIS_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret")
    monkeypatch.setenv("DUFYND_JARVIS_MAX_TURNS", "8")
    monkeypatch.setenv("DUFYND_JARVIS_MAX_BUDGET_USD", "0.25")

    options = jarvis_runtime.make_safe_worker_options(BudgetBridge())

    assert options.max_budget_usd == 0.2


def test_runtime_readiness_reports_autonomous_switch(monkeypatch) -> None:
    monkeypatch.setenv("DUFYND_JARVIS_ACTIVE", "1")
    monkeypatch.setenv("DUFYND_JARVIS_AUTONOMOUS", "1")
    monkeypatch.setenv("DUFYND_JARVIS_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret")

    readiness = runtime_readiness()

    assert readiness["autonomous"] is True
    assert readiness["ready_for_autonomous_cycle"] is True


def test_autonomous_session_requires_explicit_switch(monkeypatch) -> None:
    monkeypatch.setenv("DUFYND_JARVIS_ACTIVE", "1")
    monkeypatch.delenv("DUFYND_JARVIS_AUTONOMOUS", raising=False)
    monkeypatch.setenv("DUFYND_JARVIS_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret")
    monkeypatch.setenv("DUFYND_JARVIS_BUDGET_ID", "jarvis_activation_pilot_001")

    with pytest.raises(RuntimeError, match="autonomous cycle is disabled"):
        _require_autonomous_session(BudgetBridge(can_run=True))


def test_autonomous_session_requires_active_budget(monkeypatch) -> None:
    monkeypatch.setenv("DUFYND_JARVIS_ACTIVE", "1")
    monkeypatch.setenv("DUFYND_JARVIS_AUTONOMOUS", "1")
    monkeypatch.setenv("DUFYND_JARVIS_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret")
    monkeypatch.setenv("DUFYND_JARVIS_BUDGET_ID", "jarvis_activation_pilot_001")

    with pytest.raises(RuntimeError, match="does not permit another run"):
        _require_autonomous_session(BudgetBridge(can_run=False))


def test_runtime_readiness_is_safe_by_default(monkeypatch) -> None:
    for name in (
        "DUFYND_JARVIS_ACTIVE",
        "DUFYND_JARVIS_MODEL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    readiness = runtime_readiness()

    assert readiness["active"] is False
    assert readiness["ready_for_model_execution"] is False


def test_runtime_refuses_model_execution_without_explicit_activation(monkeypatch) -> None:
    monkeypatch.delenv("DUFYND_JARVIS_ACTIVE", raising=False)
    monkeypatch.setenv("DUFYND_JARVIS_MODEL", "test-model")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret")

    with pytest.raises(RuntimeError, match="active model execution is disabled"):
        _require_active_runtime()


def test_runtime_activation_requires_explicit_model(monkeypatch) -> None:
    monkeypatch.setenv("DUFYND_JARVIS_ACTIVE", "1")
    monkeypatch.delenv("DUFYND_JARVIS_MODEL", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret")

    with pytest.raises(RuntimeError, match="DUFYND_JARVIS_MODEL"):
        _require_active_runtime()


def test_runtime_clamps_turns_and_budget(monkeypatch) -> None:
    monkeypatch.setenv("DUFYND_JARVIS_ACTIVE", "1")
    monkeypatch.setenv("DUFYND_JARVIS_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret")
    monkeypatch.setenv("DUFYND_JARVIS_MAX_TURNS", "99")
    monkeypatch.setenv("DUFYND_JARVIS_MAX_BUDGET_USD", "5")

    model, max_turns, max_budget_usd = _require_active_runtime()

    assert model == "claude-sonnet-5"
    assert max_turns == 12
    assert max_budget_usd == 1.0


def test_runtime_namespaces_agent_created_ids() -> None:
    assert _require_runtime_id("jarvis_idea_test", "jarvis_idea_") == "jarvis_idea_test"

    with pytest.raises(ValueError, match="jarvis_idea_"):
        _require_runtime_id("idea_existing_human", "jarvis_idea_")


def test_runtime_requires_active_budget_window(monkeypatch) -> None:
    monkeypatch.setenv("DUFYND_JARVIS_BUDGET_ID", "jarvis_activation_pilot_001")
    monkeypatch.setenv("DUFYND_JARVIS_MODEL", "claude-sonnet-5")

    budget_id, status = _require_budget_window(BudgetBridge(can_run=True))

    assert budget_id == "jarvis_activation_pilot_001"
    assert status["can_run"] is True

    with pytest.raises(RuntimeError, match="does not permit another run"):
        _require_budget_window(BudgetBridge(can_run=False))


def test_runtime_rejects_budget_window_expanded_beyond_human_approval(monkeypatch) -> None:
    monkeypatch.setenv("DUFYND_JARVIS_BUDGET_ID", "jarvis_activation_pilot_001")
    monkeypatch.setenv("DUFYND_JARVIS_MODEL", "claude-sonnet-5")

    with pytest.raises(RuntimeError, match="exceeds its approved human limits"):
        _require_budget_window(
            BudgetBridge(
                can_run=True,
                max_runs=20,
                approved_max_runs=10,
            )
        )


def test_runtime_rejects_cap_expanded_beyond_human_approval(monkeypatch) -> None:
    monkeypatch.setenv("DUFYND_JARVIS_BUDGET_ID", "jarvis_activation_pilot_001")
    monkeypatch.setenv("DUFYND_JARVIS_MODEL", "claude-sonnet-5")

    with pytest.raises(RuntimeError, match="exceeds its approved human limits"):
        _require_budget_window(
            BudgetBridge(
                can_run=True,
                cap_usd=5.0,
                approved_cap_usd=2.5,
            )
        )


def test_runtime_rejects_configured_per_run_cap_above_human_approval(monkeypatch) -> None:
    monkeypatch.setenv("DUFYND_JARVIS_BUDGET_ID", "jarvis_activation_pilot_001")
    monkeypatch.setenv("DUFYND_JARVIS_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("DUFYND_JARVIS_MAX_BUDGET_USD", "0.50")

    with pytest.raises(RuntimeError, match="configured per-run budget exceeds"):
        _require_budget_window(
            BudgetBridge(
                can_run=True,
                approved_per_run_cap_usd=0.25,
            )
        )


def test_autonomous_event_limit_is_bounded() -> None:
    assert _bounded_autonomous_max_events(-1) == 0
    assert _bounded_autonomous_max_events(2) == 2
    assert _bounded_autonomous_max_events(999) == 5


def test_autonomous_cycle_defers_safe_task_when_inbox_backlog_remains(monkeypatch, capsys) -> None:
    bridge = SupervisorBridge(pending=3)

    monkeypatch.setattr(
        jarvis_runtime,
        "_require_autonomous_session",
        lambda _bridge: ("budget", {"can_run": True}),
    )

    async def fake_process_loop(_bridge, *, max_events):
        assert max_events == 2
        return 0

    safe_called = False

    async def fake_safe_task(_bridge):
        nonlocal safe_called
        safe_called = True
        return 0

    monkeypatch.setattr(jarvis_runtime, "process_loop", fake_process_loop)
    monkeypatch.setattr(jarvis_runtime, "process_safe_task", fake_safe_task)

    result = asyncio.run(process_autonomous_cycle(bridge, max_events=2))

    assert result == 0
    assert safe_called is False
    assert "inbox backlog remains" in capsys.readouterr().out.lower()


def test_autonomous_cycle_runs_safe_task_after_inbox_is_clear(monkeypatch, capsys) -> None:
    bridge = SupervisorBridge(pending=0)
    bridge.load_autonomy_queue = lambda: {
        "safe_to_execute": [
            {
                "task_id": "repo_current_commerce",
                "domain": "commerce",
                "requires_human_approval": False,
            }
        ]
    }

    monkeypatch.setattr(
        jarvis_runtime,
        "_require_autonomous_session",
        lambda _bridge: ("budget", {"can_run": True}),
    )

    safe_called = False
    branch_called = False

    async def fake_safe_task(_bridge):
        nonlocal safe_called
        safe_called = True
        return 0

    async def fake_branch_task(_bridge):
        nonlocal branch_called
        branch_called = True
        return 0

    monkeypatch.setattr(jarvis_runtime, "process_safe_task", fake_safe_task)
    monkeypatch.setattr(jarvis_runtime, "process_branch_task", fake_branch_task)

    result = asyncio.run(process_autonomous_cycle(bridge, max_events=0))

    assert result == 0
    assert safe_called is True
    assert branch_called is False
    output = capsys.readouterr().out.lower()
    assert "worker=safe_worker" in output


def test_autonomous_cycle_routes_engineering_to_branch_worker(monkeypatch, capsys) -> None:
    bridge = SupervisorBridge(pending=0)
    bridge.load_autonomy_queue = lambda: {
        "safe_to_execute": [
            {
                "task_id": "repo_current_engineering",
                "domain": "engineering",
                "requires_human_approval": False,
            }
        ]
    }

    monkeypatch.setattr(
        jarvis_runtime,
        "_require_autonomous_session",
        lambda _bridge: ("budget", {"can_run": True}),
    )

    safe_called = False
    branch_called = False

    async def fake_safe_task(_bridge):
        nonlocal safe_called
        safe_called = True
        return 0

    async def fake_branch_task(_bridge):
        nonlocal branch_called
        branch_called = True
        return 0

    monkeypatch.setattr(jarvis_runtime, "process_safe_task", fake_safe_task)
    monkeypatch.setattr(jarvis_runtime, "process_branch_task", fake_branch_task)

    result = asyncio.run(process_autonomous_cycle(bridge, max_events=0))

    assert result == 0
    assert safe_called is False
    assert branch_called is True
    output = capsys.readouterr().out.lower()
    assert "worker=branch_worker" in output


def test_autonomous_cycle_exits_cleanly_when_no_safe_task_exists(monkeypatch, capsys) -> None:
    bridge = SupervisorBridge(pending=0)
    bridge.load_autonomy_queue = lambda: {"safe_to_execute": []}

    monkeypatch.setattr(
        jarvis_runtime,
        "_require_autonomous_session",
        lambda _bridge: ("budget", {"can_run": True}),
    )

    safe_called = False
    branch_called = False

    async def fake_safe_task(_bridge):
        nonlocal safe_called
        safe_called = True
        return 0

    async def fake_branch_task(_bridge):
        nonlocal branch_called
        branch_called = True
        return 0

    monkeypatch.setattr(jarvis_runtime, "process_safe_task", fake_safe_task)
    monkeypatch.setattr(jarvis_runtime, "process_branch_task", fake_branch_task)

    result = asyncio.run(process_autonomous_cycle(bridge, max_events=0))

    assert result == 0
    assert safe_called is False
    assert branch_called is False
    output = capsys.readouterr().out.lower()
    assert "worker=none" in output


def test_supervisor_event_limit_is_bounded() -> None:
    assert _bounded_supervisor_max_events(0) == 1
    assert _bounded_supervisor_max_events(8) == 8
    assert _bounded_supervisor_max_events(999) == 20


def test_process_loop_drains_multiple_events_without_reapproval(monkeypatch, capsys) -> None:
    bridge = SupervisorBridge(pending=5)

    async def fake_process_next_outcome(target):
        target.pending -= 1
        return 0, True

    monkeypatch.setattr(jarvis_runtime, "_process_next_outcome", fake_process_next_outcome)

    result = asyncio.run(jarvis_runtime.process_loop(bridge, max_events=3))

    assert result == 0
    assert bridge.pending == 2
    output = capsys.readouterr().out
    assert "processed=3" in output
    assert "model_events=3" in output
    assert "stop_reason=max_model_events_reached" in output


def test_process_loop_deterministic_event_does_not_consume_model_limit(monkeypatch, capsys) -> None:
    bridge = SupervisorBridge(pending=3)
    outcomes = iter([(0, False), (0, True), (0, True)])

    async def fake_process_next_outcome(target):
        target.pending -= 1
        return next(outcomes)

    monkeypatch.setattr(jarvis_runtime, "_process_next_outcome", fake_process_next_outcome)

    result = asyncio.run(jarvis_runtime.process_loop(bridge, max_events=2))

    assert result == 0
    assert bridge.pending == 0
    output = capsys.readouterr().out
    assert "processed=3" in output
    assert "model_events=2" in output
    assert "deterministic_events=1" in output


def test_process_loop_stops_when_inbox_is_empty(monkeypatch, capsys) -> None:
    bridge = SupervisorBridge(pending=0)
    called = False

    async def fake_process_next(_target):
        nonlocal called
        called = True
        return 0, True

    monkeypatch.setattr(jarvis_runtime, "_process_next_outcome", fake_process_next)

    result = asyncio.run(jarvis_runtime.process_loop(bridge, max_events=8))

    assert result == 0
    assert called is False
    assert "stop_reason=inbox_empty" in capsys.readouterr().out


def test_process_loop_stops_safely_at_runtime_or_budget_gate(monkeypatch, capsys) -> None:
    bridge = SupervisorBridge(pending=2)

    async def fake_process_next(_target):
        raise RuntimeError("budget window does not permit another run")

    monkeypatch.setattr(jarvis_runtime, "_process_next_outcome", fake_process_next)

    result = asyncio.run(jarvis_runtime.process_loop(bridge, max_events=8))

    assert result == 0
    output = capsys.readouterr().out
    assert "stopped safely" in output
    assert "stop_reason=runtime_or_budget_gate" in output


def test_runtime_readiness_supports_module_execution() -> None:
    env = os.environ.copy()
    for name in (
        "DUFYND_JARVIS_ACTIVE",
        "DUFYND_JARVIS_MODEL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
    ):
        env.pop(name, None)

    completed = subprocess.run(
        [sys.executable, "-m", "scripts.dufynd_jarvis_runtime", "--readiness"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(completed.stdout)

    assert payload["active"] is False
    assert payload["ready_for_model_execution"] is False
