from __future__ import annotations

from scripts.dufynd_jarvis_freshness import (
    evaluate_freshness,
    latest_context_timestamp,
    parse_timestamp,
    repo_control_plane_marker,
)


def marker(
    fingerprint: str,
    *,
    verified_at: str = "2026-09-29T15:47:18+00:00",
) -> dict:
    return {
        "key": "jarvis.repo_control_plane",
        "value": {
            "source_fingerprint_sha256": fingerprint,
            "repo_generated_at": "2026-09-29T15:47:18+00:00",
        },
        "last_verified_at": verified_at,
        "updated_at": verified_at,
    }


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


def test_repo_control_plane_marker_ignores_unrelated_recent_rows() -> None:
    rows = [
        {
            "key": "content.active_strategy",
            "last_verified_at": "2026-09-29T16:00:00+00:00",
        },
        marker("expected"),
    ]

    selected = repo_control_plane_marker(rows)

    assert selected is not None
    assert selected["value"]["source_fingerprint_sha256"] == "expected"


def test_freshness_blocks_missing_repo_sync_even_with_recent_unrelated_context() -> None:
    report = evaluate_freshness(
        {
            "generated_at": "2026-09-29T15:47:18+00:00",
            "source_fingerprint_sha256": "repo-fingerprint",
        },
        {
            "master_status": [
                {
                    "key": "content.active_strategy",
                    "last_verified_at": "2026-09-29T16:00:00+00:00",
                    "updated_at": "2026-09-29T16:00:00+00:00",
                }
            ]
        },
    )

    assert report["stale"] is True
    assert report["safe_to_use_autonomy_queue"] is False
    assert "repo_control_plane_sync_missing" in report["reasons"]


def test_freshness_blocks_fingerprint_mismatch() -> None:
    report = evaluate_freshness(
        {
            "generated_at": "2026-09-29T15:47:18+00:00",
            "source_fingerprint_sha256": "repo-fingerprint",
        },
        {"master_status": [marker("older-fingerprint")]},
    )

    assert report["stale"] is True
    assert report["safe_to_use_autonomy_queue"] is False
    assert "repo_control_plane_fingerprint_mismatch" in report["reasons"]
    assert report["supabase_source_fingerprint_sha256"] == "older-fingerprint"


def test_freshness_allows_exact_recent_repo_sync() -> None:
    report = evaluate_freshness(
        {
            "generated_at": "2026-09-29T15:47:18+00:00",
            "source_fingerprint_sha256": "repo-fingerprint",
        },
        {"master_status": [marker("repo-fingerprint")]},
    )

    assert report["stale"] is False
    assert report["safe_to_use_autonomy_queue"] is True
    assert report["reasons"] == []
    assert report["lag_hours"] == 0.0


def test_freshness_blocks_matching_but_old_sync_marker() -> None:
    report = evaluate_freshness(
        {
            "generated_at": "2026-09-29T15:47:18+00:00",
            "source_fingerprint_sha256": "repo-fingerprint",
        },
        {
            "master_status": [
                marker(
                    "repo-fingerprint",
                    verified_at="2026-09-27T15:47:18+00:00",
                )
            ]
        },
        max_lag_hours=24,
    )

    assert report["stale"] is True
    assert "repo_control_plane_sync_too_old" in report["reasons"]


def test_freshness_blocks_repo_without_fingerprint() -> None:
    report = evaluate_freshness(
        {"generated_at": "2026-09-29T15:47:18+00:00"},
        {"master_status": [marker("repo-fingerprint")]},
    )

    assert report["stale"] is True
    assert "repo_source_fingerprint_missing" in report["reasons"]
