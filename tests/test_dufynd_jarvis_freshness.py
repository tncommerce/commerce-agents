from __future__ import annotations

from datetime import UTC, datetime, timedelta

from scripts.dufynd_jarvis_freshness import (
    evaluate_freshness,
    find_repo_snapshot,
    parse_timestamp,
)
from scripts.sync_dufynd_repo_state_to_supabase import SNAPSHOT_KEY

CHECKED_AT = datetime(2026, 9, 29, 15, 48, tzinfo=UTC)


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
        now=CHECKED_AT,
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
        now=CHECKED_AT,
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
        {"master_status": [snapshot_row(generated_at="2026-09-21T19:00:16+00:00")]},
        max_lag_hours=24,
        now=CHECKED_AT,
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
        now=CHECKED_AT,
    )

    assert report["stale"] is False
    assert report["safe_to_use_autonomy_queue"] is True
    assert report["reasons"] == []
    assert report["lag_hours"] == 0.0


def test_freshness_blocks_missing_repo_fingerprint() -> None:
    report = evaluate_freshness(
        {"generated_at": "2026-09-29T15:47:18+00:00"},
        {"master_status": [snapshot_row()]},
        now=CHECKED_AT,
    )

    assert report["stale"] is True
    assert "repo_source_fingerprint_missing" in report["reasons"]


def test_matching_weeks_old_snapshots_are_not_safe() -> None:
    stamp = "2026-10-09T13:19:11+00:00"
    report = evaluate_freshness(
        {"generated_at": stamp, "source_fingerprint_sha256": "identical"},
        {"master_status": [snapshot_row(generated_at=stamp, fingerprint="identical")]},
        max_lag_hours=0,
        max_snapshot_age_hours=48,
        now=datetime(2026, 11, 2, 5, 35, tzinfo=UTC),
    )
    assert report["stale"] is True
    assert report["safe_to_use_autonomy_queue"] is False
    assert report["lag_hours"] == 0
    assert {"repo_snapshot_expired", "supabase_snapshot_expired"} <= set(report["reasons"])
    assert report["repo_age_hours"] > 500
    assert report["supabase_age_hours"] > 500


def test_future_snapshot_is_blocked_and_short_clock_skew_is_allowed() -> None:
    now = datetime(2026, 11, 2, 6, 0, tzinfo=UTC)
    future = (now + timedelta(hours=1)).isoformat()
    rejected = evaluate_freshness(
        {"generated_at": future, "source_fingerprint_sha256": "same"},
        {"master_status": [snapshot_row(generated_at=future, fingerprint="same")]},
        now=now,
    )
    assert "repo_snapshot_timestamp_in_future" in rejected["reasons"]
    assert "supabase_snapshot_timestamp_in_future" in rejected["reasons"]
    assert rejected["safe_to_use_autonomy_queue"] is False

    small_skew = (now + timedelta(seconds=30)).isoformat()
    allowed = evaluate_freshness(
        {"generated_at": small_skew, "source_fingerprint_sha256": "same"},
        {"master_status": [snapshot_row(generated_at=small_skew, fingerprint="same")]},
        max_lag_hours=0,
        now=now,
    )
    assert allowed["stale"] is False


def test_exact_48_hour_age_boundary_is_not_overdue() -> None:
    now = datetime(2026, 11, 2, 6, 0, tzinfo=UTC)
    stamp = (now - timedelta(hours=48)).isoformat()
    result = evaluate_freshness(
        {"generated_at": stamp, "source_fingerprint_sha256": "same"},
        {"master_status": [snapshot_row(generated_at=stamp, fingerprint="same")]},
        max_lag_hours=0,
        max_snapshot_age_hours=48,
        now=now,
    )
    assert result["stale"] is False
    assert result["repo_age_hours"] == 48
    assert result["supabase_age_hours"] == 48
    assert result["checked_at"] == now.isoformat()
