from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/dufynd-pilot-previews.yml")
LEGACY_WORKFLOWS = (
    Path(".github/workflows/scentai-pilot-preview.yml"),
    Path(".github/workflows/scentai-pilot-batch02-preview.yml"),
    Path(".github/workflows/scentai-pilot-batch03-preview.yml"),
)


def test_dufynd_has_one_preview_and_state_writer() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "group: dufynd-pilot-previews-scentai-mvp" in text
    assert "cancel-in-progress: true" in text
    assert "Render all DUFYND pilot previews" in text
    assert "Refresh DUFYND derived state once" in text

    for legacy in LEGACY_WORKFLOWS:
        assert not legacy.exists(), legacy
