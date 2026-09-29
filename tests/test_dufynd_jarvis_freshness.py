from __future__ import annotations

from scripts.dufynd_jarvis_freshness import (
    evaluate_freshness,
    latest_context_timestamp,
    parse_timestamp,
)


def test_parse_timestamp_normalizes_utc() -> None:
    parsed = parse_timestamp("2026-09-29T15:47:18Z")

    assert parsed is not None
    assert parsed.isoformat() == "2026-09-29T15:47:18+00:00"


def test_latest_context_timestamp_uses_verified_or_updated_values() -> None:
    latest = latest_context_timestamp(
        [
            {
                "last_verified_at": "2026-09-20T10:00:00+00:00",
                "updated_at": "2026-09-20T11:00:00+00:00",
            },
            {
                "last_verified_at": "2026-09-21T12:00:00+00:00",
                "updated_at": "2026-09-21T11:00:00+00:00",
            },
        ]
    )

    assert latest is not None
    assert latest.isoformat() == "2026-09-21T12:00:00+00:00"


def test_freshness_blocks_stale_supabase_control_plane() -> None:
    report = evaluate_freshness(
        {
            "generated_at": "2026-09-29T15:47:18+00:00",
            "source_fingerprint_sha256": "repo-fingerprint",
        },
        {
            "master_status": [
                {
                    "last_verified_at": "2026-09-21T19:00:16+00:00",
                    "updated_at": "2026-09-21T19:00:16+00:00",
                }
            ]
        },
        max_lag_hours=24,
    )

    assert report["stale"] is True
    assert report["safe_to_use_autonomy_queue"] is False
    assert "supabase_control_plane_older_than_repo" in report["reasons"]
    assert report["lag_hours"] is not None
    assert report["lag_hours"] > 24


def test_freshness_allows_recent_supabase_control_plane() -> None:
    report = evaluate_freshness(
        {"generated_at": "2026-09-29T15:47:18+00:00"},
        {
            "master_status": [
                {
                    "last_verified_at": "2026-09-29T14:47:18+00:00",
                    "updated_at": "2026-09-29T14:47:18+00:00",
                }
            ]
        },
        max_lag_hours=24,
    )

    assert report["stale"] is False
    assert report["safe_to_use_autonomy_queue"] is True
    assert report["reasons"] == []


def test_freshness_blocks_missing_supabase_timestamp() -> None:
    report = evaluate_freshness(
        {"generated_at": "2026-09-29T15:47:18+00:00"},
        {"master_status": []},
    )

    assert report["stale"] is True
    assert report["safe_to_use_autonomy_queue"] is False
    assert report["reasons"] == ["supabase_master_status_timestamp_missing"]


def test_freshness_allows_supabase_context_newer_than_repo() -> None:
    report = evaluate_freshness(
        {"generated_at": "2026-09-29T15:47:18+00:00"},
        {
            "master_status": [
                {
                    "last_verified_at": "2026-09-29T16:47:18+00:00",
                    "updated_at": "2026-09-29T16:47:18+00:00",
                }
            ]
        },
    )

    assert report["stale"] is False
    assert report["lag_hours"] == -1.0
