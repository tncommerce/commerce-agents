"""Keep the true-3D review workflow manual, read-only and review-only."""

from pathlib import Path

WORKFLOW = Path(".github/workflows/dufynd-model3d-review.yml")


def test_model3d_review_workflow_is_manual_and_read_only() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in source
    assert "permissions:\n  contents: read" in source
    assert "\npush:" not in source
    assert "\npull_request:" not in source


def test_model3d_review_workflow_builds_portable_review_artifact() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "scripts/build_scentai_model3d_review_bundle.py" in source
    assert "actions/upload-artifact@" in source
    assert "dufynd-model3d-review-" in source
    assert "retention-days: 7" in source


def test_model3d_review_workflow_cannot_approve_models() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "approve_scentai_model3d.py" not in source
    assert "--human-visual-approval" not in source
    assert "--write" not in source
