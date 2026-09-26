"""Temporary diagnostic: emit expected DUFYND Jarvis state nodes for canonical offer refresh."""

from __future__ import annotations

import json

from scripts.refresh_scentai_jarvis_state import refresh_state
from scripts.validate_scentai_jarvis_state_graph import load_current_state


def test_emit_expected_drifted_jarvis_nodes() -> None:
    current = load_current_state()
    generated_at = str(current["operations"]["generated_at"])
    expected = refresh_state(generated_at=generated_at)

    drifted = [
        key
        for key in ("master_status", "operations", "release_pipeline", "release_status")
        if current[key] != expected[key]
    ]

    for key in drifted:
        print(f"DUFYND_STATE_BEGIN::{key}")
        print(json.dumps(expected[key], ensure_ascii=False, separators=(",", ":")))
        print(f"DUFYND_STATE_END::{key}")

    assert not drifted, f"diagnostic expected drift: {drifted}"
