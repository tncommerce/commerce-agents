from __future__ import annotations

from scripts.dufynd_legacy_preview_policy import (
    evaluate_legacy_preview_policy,
)


def test_high_end_rnd_holds_legacy_preview_rendering() -> None:
    policy = evaluate_legacy_preview_policy(
        {
            "active_track": "high_end_rnd",
            "legacy_pilot_batches": "hold",
        }
    )

    assert policy.render is False
    assert policy.reason == "legacy_pilots_on_hold_for_high_end_rnd"


def test_active_legacy_pipeline_allows_preview_rendering() -> None:
    policy = evaluate_legacy_preview_policy(
        {
            "active_track": "legacy_pilot_production",
            "legacy_pilot_batches": "active",
        }
    )

    assert policy.render is True
    assert policy.reason == "legacy_pilot_rendering_active"


def test_manual_force_overrides_high_end_rnd_hold() -> None:
    policy = evaluate_legacy_preview_policy(
        {
            "active_track": "high_end_rnd",
            "legacy_pilot_batches": "hold",
        },
        force=True,
    )

    assert policy.render is True
    assert policy.reason == "manual_force_requested"


def test_missing_strategy_keeps_safe_legacy_behavior() -> None:
    policy = evaluate_legacy_preview_policy(None)

    assert policy.render is True
    assert policy.reason == "no_content_strategy_found"
