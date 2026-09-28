from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/dufynd-awin-feed-revalidation.yml")
RUNBOOK = Path("examples/retail/data/scentai_affiliate_feed_activation_runbook.md")


def test_awin_revalidation_workflow_stays_manual_and_read_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "permissions:\n  contents: read" in text
    assert "AWIN_DATA_FEED_API_KEY" in text
    assert "secrets.AWIN_DATA_FEED_API_KEY" in text
    assert "RUNNER_TEMP" in text

    assert "top-parfuemerie.csv" in text
    assert "merchant-feed-image-candidates.json" in text
    assert "release-readiness.json" in text
    assert "awin-feed-metadata.json" in text

    artifact_block = text.split("Upload sanitized review packet", 1)[1]
    assert "top-parfuemerie.csv" not in artifact_block
    assert "AWIN_DATA_FEED_API_KEY" not in artifact_block


def test_awin_revalidation_runbook_preserves_human_image_gate() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    assert ".github/workflows/dufynd-awin-feed-revalidation.yml" in text
    assert "AWIN_DATA_FEED_API_KEY" in text
    assert "31081" in text
    assert "91379" in text
    assert "never uploads or commits the raw feed" in text
    assert "final visual identity approval remains a human gate" in text
