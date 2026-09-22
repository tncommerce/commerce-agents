from __future__ import annotations

import pytest
from scripts.dufynd_openrouter_worker import (
    DEFAULT_MODEL,
    SYSTEM_PROMPT,
    _require_internal_context_allowed,
    _require_model,
    build_payload,
    runtime_readiness,
)


def test_openrouter_worker_is_free_and_read_only_by_default(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("DUFYND_OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("DUFYND_OPENROUTER_ALLOW_PAID", raising=False)
    monkeypatch.delenv(
        "DUFYND_OPENROUTER_ALLOW_INTERNAL_CONTEXT",
        raising=False,
    )

    readiness = runtime_readiness()

    assert readiness["model"] == DEFAULT_MODEL
    assert readiness["free_model"] is True
    assert readiness["paid_models_allowed"] is False
    assert readiness["internal_context_allowed"] is False
    assert readiness["ready_for_read_only_request"] is False


def test_openrouter_worker_refuses_paid_model_without_explicit_gate(
    monkeypatch,
) -> None:
    monkeypatch.delenv("DUFYND_OPENROUTER_ALLOW_PAID", raising=False)

    with pytest.raises(RuntimeError, match="Paid OpenRouter models are disabled"):
        _require_model("anthropic/claude-sonnet-4")


def test_openrouter_worker_allows_paid_model_only_with_explicit_gate(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DUFYND_OPENROUTER_ALLOW_PAID", "1")

    model = _require_model("anthropic/claude-sonnet-4")

    assert model == "anthropic/claude-sonnet-4"


def test_openrouter_worker_blocks_internal_context_by_default(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "DUFYND_OPENROUTER_ALLOW_INTERNAL_CONTEXT",
        raising=False,
    )

    with pytest.raises(RuntimeError, match="Internal DUFYND context is disabled"):
        _require_internal_context_allowed()


def test_openrouter_worker_payload_preserves_human_gates() -> None:
    payload = build_payload(
        "Review this public code for duplicated logic.",
        model=DEFAULT_MODEL,
        max_tokens=1234,
    )

    assert payload["model"] == DEFAULT_MODEL
    assert payload["max_tokens"] == 1234
    assert "read-only analysis worker" in SYSTEM_PROMPT
    assert "You must not claim that you published content" in SYSTEM_PROMPT
    assert payload["messages"][1]["content"].startswith(
        "Review this public code"
    )
