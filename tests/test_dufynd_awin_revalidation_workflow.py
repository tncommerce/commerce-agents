from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/dufynd-awin-feed-revalidation.yml")
RUNBOOK = Path("examples/retail/data/scentai_affiliate_feed_activation_runbook.md")


def test_awin_revalidation_workflow_stays_manual_read_only_and_secret_safe() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "permissions:\n  contents: read" in text
    assert "secrets.AWIN_DATA_FEED_API_KEY" in text
    assert "pip install -r requirements-dev.txt" in text
    assert "RUNNER_TEMP" in text
    assert "Prepare Release 01 feed-image review candidates" in text
    assert "scripts/prepare_scentai_feed_image_review.py" in text
    assert "release01-feed-image-review-candidates.json" in text
    assert "Render visual image review packet" in text
    assert "scripts/render_scentai_feed_image_review_html.py" in text
    assert "release01-feed-image-review.html" in text
    assert "Prepare mapped catalog feed-image review candidates" in text
    assert "scripts/prepare_scentai_catalog_feed_image_review.py" in text
    assert "catalog-feed-image-review-candidates.json" in text
    assert "Render mapped catalog visual image review packet" in text
    assert "catalog-feed-image-review.html" in text
    assert "Upload sanitized review packet" in text

    artifact_block = text.split("Upload sanitized review packet", 1)[1]
    assert "top-parfuemerie.csv" not in artifact_block
    assert "merchant-feed-image-candidates.json" not in artifact_block
    assert "AWIN_DATA_FEED_API_KEY" not in artifact_block
    assert "release01-feed-image-review-candidates.json" in artifact_block
    assert "release01-feed-image-review.html" in artifact_block
    assert "catalog-feed-image-review-candidates.json" in artifact_block
    assert "catalog-feed-image-review.html" in artifact_block


def test_blocked_release_still_builds_review_packet_before_preserving_failure() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    check_pos = text.index("Check Release 01 against current feed")
    extract_pos = text.index("Extract review-only image candidates")
    prepare_pos = text.index("Prepare Release 01 feed-image review candidates")
    catalog_prepare_pos = text.index("Prepare mapped catalog feed-image review candidates")
    render_pos = text.index("Render visual image review packet")
    catalog_render_pos = text.index("Render mapped catalog visual image review packet")
    upload_pos = text.index("Upload sanitized review packet")
    preserve_pos = text.index("Preserve blocked Release 01 result after review artifact")

    assert (
        check_pos
        < extract_pos
        < prepare_pos
        < catalog_prepare_pos
        < render_pos
        < catalog_render_pos
        < upload_pos
        < preserve_pos
    )
    assert "id: release_check" in text
    assert 'echo "status=$status" >> "$GITHUB_OUTPUT"' in text
    assert 'if [ "$status" -eq 20 ]; then' in text
    assert "continuing only through the independently guarded human image-review path" in text
    assert "steps.release_check.outputs.status == '20'" in text
    assert "Review artifact was generated for human image review only." in text
    assert "exit 20" in text


def test_awin_revalidation_runbook_keeps_raw_feed_and_approval_boundaries() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    assert ".github/workflows/dufynd-awin-feed-revalidation.yml" in text
    assert "AWIN_DATA_FEED_API_KEY" in text
    assert "Awin advertiser ID: `31081`" in text
    assert "Awin feed ID: `91379`" in text
    assert "raw feed only into runner-temporary" in text
    assert "It never approves an image" in text
    assert "expected safety gate, not a feed failure" in text
