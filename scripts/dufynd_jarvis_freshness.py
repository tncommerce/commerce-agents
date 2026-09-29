from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.sync_dufynd_repo_state_to_supabase import SNAPSHOT_KEY

DEFAULT_REPO_STATUS_PATH = Path("examples/retail/data/scentai_jarvis_master_status.json")
DEFAULT_MAX_LAG_HOURS = 24.0


def parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def find_repo_snapshot(
    master_status: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for row in master_status:
        if row.get("key") == SNAPSHOT_KEY:
            return row
    return None


def evaluate_freshness(
    repo_status: dict[str, Any],
    supabase_context: dict[str, Any],
    *,
    max_lag_hours: float = DEFAULT_MAX_LAG_HOURS,
) -> dict[str, Any]:
    allowed_lag = max(0.0, float(max_lag_hours))
    repo_generated_at = parse_timestamp(repo_status.get("generated_at"))
    repo_fingerprint = str(repo_status.get("source_fingerprint_sha256") or "").strip()

    master_status = supabase_context.get("master_status") or []
    if not isinstance(master_status, list):
        master_status = []

    snapshot = find_repo_snapshot(master_status)
    snapshot_value = snapshot.get("value") if isinstance(snapshot, dict) else None
    if not isinstance(snapshot_value, dict):
        snapshot_value = {}

    supabase_generated_at = parse_timestamp(snapshot_value.get("generated_at"))
    if supabase_generated_at is None and isinstance(snapshot, dict):
        supabase_generated_at = parse_timestamp(snapshot.get("last_verified_at"))

    supabase_fingerprint = str(
        snapshot_value.get("source_fingerprint_sha256") or ""
    ).strip()

    reasons: list[str] = []
    lag_hours: float | None = None

    if repo_generated_at is None:
        reasons.append("repo_generated_at_missing_or_invalid")
    if not repo_fingerprint:
        reasons.append("repo_source_fingerprint_missing")
    if snapshot is None:
        reasons.append("repo_state_snapshot_missing")
    if snapshot is not None and supabase_generated_at is None:
        reasons.append("repo_state_snapshot_timestamp_missing")
    if snapshot is not None and not supabase_fingerprint:
        reasons.append("repo_state_snapshot_fingerprint_missing")

    if repo_fingerprint and supabase_fingerprint and repo_fingerprint != supabase_fingerprint:
        reasons.append("repo_state_snapshot_fingerprint_mismatch")

    if repo_generated_at is not None and supabase_generated_at is not None:
        lag_hours = (repo_generated_at - supabase_generated_at).total_seconds() / 3600
        if lag_hours > allowed_lag:
            reasons.append("supabase_control_plane_older_than_repo")

    stale = bool(reasons)

    return {
        "stale": stale,
        "safe_to_use_autonomy_queue": not stale,
        "snapshot_key": SNAPSHOT_KEY,
        "max_lag_hours": allowed_lag,
        "lag_hours": lag_hours,
        "repo_generated_at": (
            repo_generated_at.isoformat() if repo_generated_at is not None else None
        ),
        "supabase_generated_at": (
            supabase_generated_at.isoformat() if supabase_generated_at is not None else None
        ),
        "repo_source_fingerprint_sha256": repo_fingerprint or None,
        "supabase_source_fingerprint_sha256": supabase_fingerprint or None,
        "reasons": reasons,
    }


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare the repository Jarvis master snapshot with the durable "
            "Supabase Jarvis control-plane snapshot before autonomous task selection."
        )
    )
    parser.add_argument("--repo-status", type=Path, default=DEFAULT_REPO_STATUS_PATH)
    parser.add_argument("--max-lag-hours", type=float, default=DEFAULT_MAX_LAG_HOURS)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    repo_status = load_json(args.repo_status)
    context = DufyndJarvisBridge().load_context()
    report = evaluate_freshness(
        repo_status,
        context,
        max_lag_hours=args.max_lag_hours,
    )

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "DUFYND Jarvis freshness | "
            f"stale={report['stale']} | "
            f"lag_hours={report['lag_hours']} | "
            f"safe_to_use_autonomy_queue={report['safe_to_use_autonomy_queue']}"
        )
        for reason in report["reasons"]:
            print(f"  - {reason}")

    return 20 if report["stale"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
