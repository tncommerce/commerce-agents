from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/dufynd-awin-feed-revalidation.yml")
RUNBOOK = Path("examples/retail/data/scentai_affiliate_feed_activation_runbook.md")


def test_awin_revalidation_workflow_stays_manual_read_only_and_secret_safe() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "permissions:\n  contents: read" in text
    assert "secrets.AWIN_DATA_FEED_API_KEY" in text
    assert "RUNNER_TEMP" in text
    assert "Upload sanitized review packet" in text

    artifact_block = text.split("Upload sanitized review packet", 1)[1]
    assert "top-parfuemerie.csv" not in artifact_block
    assert "AWIN_DATA_FEED_API_KEY" not in artifact_block


def test_awin_revalidation_runbook_keeps_raw_feed_and_approval_boundaries() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    assert ".github/workflows/dufynd-awin-feed-revalidation.yml" in text
    assert "AWIN_DATA_FEED_API_KEY" in text
    assert "Awin advertiser ID: `31081`" in text
    assert "Awin feed ID: `91379`" in text
    assert "raw feed only into runner-temporary" in text
    assert "It never approves an image" in text
    assert "expected safety gate, not a feed failure" in text
