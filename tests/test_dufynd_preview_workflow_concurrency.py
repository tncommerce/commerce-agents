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
    assert "Decide whether legacy previews should render" in text
    assert "Render all legacy DUFYND pilot previews" in text
    assert "steps.preview_policy.outputs.render == 'true'" in text
    assert "dufynd_legacy_preview_policy.py" in text
    assert "Refresh DUFYND derived state once" in text

    for legacy in LEGACY_WORKFLOWS:
        assert not legacy.exists(), legacy


def test_derived_state_only_refresh_skips_render_autodeploy() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'commit_message="Generate DUFYND pilot previews and refresh state [skip ci]"' in text
    assert 'commit_message="$commit_message [skip render]"' in text
    assert "^examples/retail/storefront-web/public/social/pilots/" in text
    assert "Derived-state-only commit: Render auto-deploy will be skipped." in text


def test_preview_asset_changes_keep_render_autodeploy_available() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    guard = "if ! printf '%s\\n' \"$staged_paths\" | grep -q '^examples/retail/storefront-web/public/social/pilots/'; then"
    assert guard in text
