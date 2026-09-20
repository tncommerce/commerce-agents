from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys

import pytest
from scripts.dufynd_jarvis_runtime import (
    SYSTEM_PROMPT,
    _require_active_runtime,
    _require_budget_window,
    _require_runtime_id,
    allowed_tool_names,
    event_prompt,
    process_next,
    runtime_readiness,
)


class EmptyBridge:
    def load_health(self):
        return {"inbox": {"pending": 0}}

    def claim_next_inbox_event(self):
        return None


class BudgetBridge:
    def __init__(self, can_run: bool = True):
        self.can_run = can_run

    def load_budget_status(self, budget_id: str):
        return {
            "budget_id": budget_id,
            "status": "active" if self.can_run else "planned",
            "model": "claude-sonnet-5",
            "can_run": self.can_run,
        }


def test_runtime_has_only_internal_safe_tool_surface() -> None:
    names = allowed_tool_names()

    assert "mcp__dufynd_jarvis__load_creative_context" in names
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


def test_process_next_is_noop_when_inbox_is_empty(capsys) -> None:
    result = asyncio.run(process_next(EmptyBridge()))

    assert result == 0
    assert "no pending event" in capsys.readouterr().out.lower()


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


def test_runtime_readiness_supports_direct_script_execution() -> None:
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
        [sys.executable, "scripts/dufynd_jarvis_runtime.py", "--readiness"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(completed.stdout)

    assert payload["active"] is False
    assert payload["ready_for_model_execution"] is False
