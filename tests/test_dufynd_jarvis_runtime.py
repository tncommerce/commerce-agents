from __future__ import annotations

import asyncio

from scripts.dufynd_jarvis_runtime import (
    SYSTEM_PROMPT,
    allowed_tool_names,
    event_prompt,
    process_next,
)


class EmptyBridge:
    def claim_next_inbox_event(self):
        return None


def test_runtime_has_only_internal_safe_tool_surface() -> None:
    names = allowed_tool_names()

    assert "mcp__dufynd_jarvis__load_creative_context" in names
    assert "mcp__dufynd_jarvis__record_lesson" in names
    assert "mcp__dufynd_jarvis__record_content_idea" in names
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
