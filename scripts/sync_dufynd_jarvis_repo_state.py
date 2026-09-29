from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.dufynd_jarvis_freshness import evaluate_freshness, load_json

DEFAULT_REPO_STATUS_PATH = Path("examples/retail/data/scentai_jarvis_master_status.json")


def sync_repo_state(
    bridge: DufyndJarvisBridge,
    repo_status: dict[str, Any],
    *,
    repo_head_sha: str | None = None,
    source_branch: str = "scentai-mvp",
) -> dict[str, Any]:
    bridge.sync_repo_control_plane(
        repo_status=repo_status,
        repo_head_sha=repo_head_sha,
        source_branch=source_branch,
    )
    context = bridge.load_context()
    return evaluate_freshness(
        repo_status,
        context,
        repo_head_sha=repo_head_sha,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sync the current repository-derived DUFYND Jarvis master state into "
            "the durable Supabase control plane and verify the exact fingerprint."
        )
    )
    parser.add_argument("--repo-status", type=Path, default=DEFAULT_REPO_STATUS_PATH)
    parser.add_argument(
        "--repo-head-sha",
        default=os.getenv("GITHUB_SHA") or None,
    )
    parser.add_argument(
        "--source-branch",
        default=os.getenv("GITHUB_REF_NAME") or "scentai-mvp",
    )
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    repo_status = load_json(args.repo_status)
    report = sync_repo_state(
        DufyndJarvisBridge(),
        repo_status,
        repo_head_sha=args.repo_head_sha,
        source_branch=args.source_branch,
    )

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "DUFYND Jarvis repo-state sync | "
            f"stale={report['stale']} | "
            f"fingerprint={report['repo_source_fingerprint_sha256']}"
        )
        for reason in report["reasons"]:
            print(f"  - {reason}")

    return 20 if report["stale"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
