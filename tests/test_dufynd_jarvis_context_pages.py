from __future__ import annotations

import asyncio
import json

import pytest
from scripts.dufynd_jarvis_context_pages import PAGE_CHARS, context_overview, context_page
from scripts.dufynd_jarvis_runtime import build_tools


def large_context():
    return {
        "idea_generation": {"patterns": [{"pattern_id": "macro", "mechanism": "ä香" * 110000}]},
        "lessons": [{"lesson_id": "reuse", "lesson": "Keep original evidence"}],
    }


def test_large_section_can_be_reconstructed_without_loss():
    payload = large_context()
    overview = context_overview(payload)
    assert len(json.dumps(overview)) < PAGE_CHARS
    assert any(row["section"] == "idea_generation.patterns" for row in overview["sections"])
    fragments = []
    offset = 0
    fingerprint = None
    while offset is not None:
        meta, fragment = context_page(payload, section="idea_generation.patterns", offset=offset)
        assert len(fragment) <= PAGE_CHARS
        fingerprint = fingerprint or meta["sha256"]
        assert meta["sha256"] == fingerprint
        fragments.append(fragment)
        offset = meta["next_offset"]
    assert json.loads("".join(fragments)) == payload["idea_generation"]["patterns"]


def test_invalid_sections_and_offsets_fail_explicitly():
    with pytest.raises(ValueError, match="Unknown context section"):
        context_page(large_context(), section="missing")
    with pytest.raises(ValueError, match="offset"):
        context_page({}, offset=-1)


def test_changed_evidence_changes_page_hash():
    before, _ = context_page({"mechanism": "macro"})
    after, _ = context_page({"mechanism": "reveal"})
    assert before["sha256"] != after["sha256"]


def test_runtime_context_tools_return_bounded_inventory_and_readable_page():
    class Bridge:
        def load_creative_context(self):
            return large_context()

        def load_context(self):
            return large_context()

    tools = {tool.name: tool for tool in build_tools(Bridge())}
    overview = asyncio.run(tools["load_creative_context"].handler({}))
    text = overview["content"][0]["text"]
    assert len(text) < PAGE_CHARS
    assert "idea_generation.patterns" in text
    page = asyncio.run(
        tools["load_context_page"].handler(
            {"context": "creative", "section": "idea_generation.patterns"}
        )
    )
    assert len(page["content"][0]["text"]) < PAGE_CHARS + 1000
    assert "ä香" in page["content"][0]["text"]
    lesson = asyncio.run(
        tools["load_context_page"].handler({"context": "operating", "section": "lessons"})
    )
    assert "Keep original evidence" in lesson["content"][0]["text"]
