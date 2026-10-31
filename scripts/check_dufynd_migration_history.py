"""Fail-closed, read-only audit of local versus exported Supabase migration history.

No database credentials, network requests, SQL execution, automatic repair,
or migration state changes. Use BEFORE anyone invokes `supabase db push`.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

LOCAL_NAME = re.compile(r"(?P<version>[0-9]{14})_(?P<name>[a-z][a-z0-9_]*)[.]sql")
REMOTE_NAME = re.compile(r"[a-z][a-z0-9_]*")
REMOTE_VERSION = re.compile(r"[0-9]{14}")


def compare_histories(local_directory: Path, remote_export: Any) -> dict[str, Any]:
    """Compare BOTH timestamp identity and semantic name; never fix automatically."""
    if not local_directory.is_dir():
        raise ValueError("local_migration_directory_missing")
    paths = sorted(local_directory.glob("*.sql"))
    if not paths:
        raise ValueError("local_migration_files_missing")
    local: list[dict[str, str]] = []
    for path in paths:
        match = LOCAL_NAME.fullmatch(path.name)
        if match is None:
            raise ValueError("local_migration_filename_invalid")
        local.append(match.groupdict())
    if not isinstance(remote_export, dict) or not isinstance(
        remote_export.get("migrations"), list
    ):
        raise ValueError("remote_export_shape_invalid")
    remote: list[dict[str, str]] = []
    for item in remote_export["migrations"]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("name"), str)
            or not isinstance(item.get("version"), str)
            or REMOTE_NAME.fullmatch(item["name"]) is None
            or REMOTE_VERSION.fullmatch(item["version"]) is None
        ):
            raise ValueError("remote_migration_record_invalid")
        remote.append({"version": item["version"], "name": item["name"]})
    if not remote:
        raise ValueError("remote_migration_history_missing")

    local_names = Counter(item["name"] for item in local)
    remote_names = Counter(item["name"] for item in remote)
    local_versions = Counter(item["version"] for item in local)
    remote_versions = Counter(item["version"] for item in remote)
    local_by_name = {item["name"]: item["version"] for item in local}
    remote_by_name = {item["name"]: item["version"] for item in remote}
    version_mismatches = [
        {"name": name, "local": version, "remote": remote_by_name[name]}
        for name, version in sorted(local_by_name.items())
        if name in remote_by_name and remote_by_name[name] != version
    ]
    missing_remote = sorted(set(local_by_name) - set(remote_by_name))
    missing_local = sorted(set(remote_by_name) - set(local_by_name))
    duplicated_local = sorted(name for name, count in local_names.items() if count > 1)
    duplicated_remote = sorted(name for name, count in remote_names.items() if count > 1)
    duplicated_versions = sorted(
        {
            version
            for version, count in (*local_versions.items(), *remote_versions.items())
            if count > 1
        }
    )
    # Compare versions explicitly even when an unrelated migration reused an ID.
    local_pairs = {(row["version"], row["name"]) for row in local}
    remote_pairs = {(row["version"], row["name"]) for row in remote}
    exact_pairs = len(local_pairs & remote_pairs)
    blocked = bool(
        version_mismatches
        or missing_local
        or missing_remote
        or duplicated_local
        or duplicated_remote
        or duplicated_versions
        or exact_pairs != len(local)
        or exact_pairs != len(remote)
    )
    return {
        "status": "BLOCKED_MIGRATION_HISTORY_DRIFT" if blocked else "ALIGNED_REVIEW_ONLY",
        "local_count": len(local),
        "remote_count": len(remote),
        "exact_pairs": exact_pairs,
        "version_mismatch_same_name": version_mismatches,
        "local_only_names": missing_remote,
        "remote_only_names": missing_local,
        "duplicate_local_names": duplicated_local,
        "duplicate_remote_names": duplicated_remote,
        "duplicate_versions": duplicated_versions,
        "safe_to_run_db_push": False if blocked else None,
        "automatic_repair_attempted": False,
        "database_writes": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-dir", type=Path, default=Path("supabase/migrations"))
    parser.add_argument("--remote-json", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = compare_histories(
            args.local_dir, json.loads(args.remote_json.read_text(encoding="utf-8"))
        )
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError):
        report = {
            "status": "BLOCKED_INPUT_INVALID",
            "safe_to_run_db_push": False,
            "automatic_repair_attempted": False,
            "database_writes": 0,
        }
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    # Even aligned histories require a separate owner-controlled database GO.
    return 0 if report["status"] == "ALIGNED_REVIEW_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
