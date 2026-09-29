from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge

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


def latest_context_timestamp(master_status: list[dict[str, Any]]) -> datetime | None:
    candidates: list[datetime] = []

    for row in master_status:
        for key in ("last_verified_at", "updated_at"):
            parsed = parse_timestamp(row.get(key))
            if parsed is not None:
                candidates.append(parsed)

    return max(candidates) if candidates else None


def evaluate_freshness(
    repo_status: dict[str, Any],
    supabase_context: dict[str, Any],
    *,
    max_lag_hours: float = DEFAULT_MAX_LAG_HOURS,
) -> dict[str, Any]:
    allowed_lag = max(0.0, float(max_lag_hours))
    repo_generated_at = parse_timestamp(repo_status.get("generated_at"))

    master_status = supabase_context.get("master_status") or []
    if not isinstance(master_status, list):
        master_status = []
    supabase_latest_at = latest_context_timestamp(master_status)

    reasons: list[str] = []
    lag_hours: float | None = None

    if repo_generated_at is None:
        reasons.append("repo_generated_at_missing_or_invalid")
    if supabase_latest_at is None:
        reasons.append("supabase_master_status_timestamp_missing")

    if repo_generated_at is not None and supabase_latest_at is not None:
        lag_hours = (repo_generated_at - supabase_latest_at).total_seconds() / 3600
        if lag_hours > allowed_lag:
            reasons.append("supabase_control_plane_older_than_repo")

    stale = bool(reasons)

    return {
        "stale": stale,
        "safe_to_use_autonomy_queue": not stale,
        "max_lag_hours": allowed_lag,
        "lag_hours": lag_hours,
        "repo_generated_at": (
            repo_generated_at.isoformat() if repo_generated_at is not None else None
        ),
        "supabase_latest_at": (
            supabase_latest_at.isoformat() if supabase_latest_at is not None else None
        ),
        "repo_source_fingerprint_sha256": repo_status.get("source_fingerprint_sha256"),
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
            "Supabase Jarvis context before autonomous task selection."
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
