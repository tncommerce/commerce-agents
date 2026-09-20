from __future__ import annotations

from pathlib import Path

WORKFLOWS = (
    Path(".github/workflows/scentai-pilot-preview.yml"),
    Path(".github/workflows/scentai-pilot-batch02-preview.yml"),
    Path(".github/workflows/scentai-pilot-batch03-preview.yml"),
)
SERIAL_GROUP = "dufynd-preview-state-writer-scentai-mvp"


def test_dufynd_preview_state_writers_share_one_serial_group() -> None:
    for path in WORKFLOWS:
        text = path.read_text(encoding="utf-8")
        assert f"group: {SERIAL_GROUP}" in text, path
        assert "cancel-in-progress: false" in text, path
