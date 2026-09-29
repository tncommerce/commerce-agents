from __future__ import annotations

from scripts.dufynd_jarvis_freshness import (
    evaluate_freshness,
    find_repo_snapshot,
    parse_timestamp,
)
from scripts.sync_dufynd_repo_state_to_supabase import SNAPSHOT_KEY


def snapshot_row(
    *,
    generated_at: str = "2026-09-29T15:47:18+00:00",
    fingerprint: str = "repo-fingerprint",
) -> dict:
    return {
        "key": SNAPSHOT_KEY,
        "value": {
            "generated_at": generated_at,
            "source_fingerprint_sha256": fingerprint,
        },
        "last_verified_at": generated_at,
    }


def test_parse_timestamp_normalizes_utc() -> None:
    parsed = parse_timestamp("2026-09-29T15:47:18Z")

    assert parsed is not None
    assert parsed.isoformat() == "2026-09-29T15:47:18+00:00"


def test_find_repo_snapshot_uses_canonical_key() -> None:
    row = snapshot_row()

    assert find_repo_snapshot([{"key": "other"}, row]) == row


def test_freshness_blocks_missing_repo_snapshot() -> None:
    report = evaluate_freshness(
        {
            "generated_at": "2026-09-29T15:47:18+00:00",
            "source_fingerprint_sha256": "repo-fingerprint",
        },
        {"master_status": []},
    )

    assert report["stale"] is True
    assert report["safe_to_use_autonomy_queue"] is False
    assert report["reasons"] == ["repo_state_snapshot_missing"]


def test_freshness_blocks_fingerprint_mismatch_even_when_timestamp_is_recent() -> None:
    report = evaluate_freshness(
        {
            "generated_at": "2026-09-29T15:47:18+00:00",
            "source_fingerprint_sha256": "new-fingerprint",
        },
        {
            "master_status": [
                snapshot_row(
                    generated_at="2026-09-29T15:47:18+00:00",
                    fingerprint="old-fingerprint",
                )
            ]
        },
    )

    assert report["stale"] is True
    assert report["safe_to_use_autonomy_queue"] is False
    assert "repo_state_snapshot_fingerprint_mismatch" in report["reasons"]
    assert report["lag_hours"] == 0.0


def test_freshness_blocks_stale_matching_snapshot() -> None:
    report = evaluate_freshness(
        {
            "generated_at": "2026-09-29T15:47:18+00:00",
            "source_fingerprint_sha256": "repo-fingerprint",
        },
        {
            "master_status": [
                snapshot_row(generated_at="2026-09-21T19:00:16+00:00")
            ]
        },
        max_lag_hours=24,
    )

    assert report["stale"] is True
    assert "supabase_control_plane_older_than_repo" in report["reasons"]
    assert report["lag_hours"] is not None
    assert report["lag_hours"] > 24


def test_freshness_allows_exact_synced_snapshot() -> None:
    report = evaluate_freshness(
        {
            "generated_at": "2026-09-29T15:47:18+00:00",
            "source_fingerprint_sha256": "repo-fingerprint",
        },
        {"master_status": [snapshot_row()]},
        max_lag_hours=0,
    )

    assert report["stale"] is False
    assert report["safe_to_use_autonomy_queue"] is True
    assert report["reasons"] == []
    assert report["lag_hours"] == 0.0


def test_freshness_blocks_missing_repo_fingerprint() -> None:
    report = evaluate_freshness(
        {"generated_at": "2026-09-29T15:47:18+00:00"},
        {"master_status": [snapshot_row()]},
    )

    assert report["stale"] is True
    assert "repo_source_fingerprint_missing" in report["reasons"]
