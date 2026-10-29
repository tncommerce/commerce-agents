"""Capture one successful fixed Render read without Gmail or activation calls."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge
from scripts.dufynd_private_observer_ingest import ArtifactError, ingest_render_artifact


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=Path("broker-render-observations.json"))
    parser.add_argument("--expected-run-id", default=os.getenv("GITHUB_RUN_ID"))
    parser.add_argument("--expected-sha", default=os.getenv("GITHUB_SHA"))
    parser.add_argument("--expected-run-attempt", default=os.getenv("GITHUB_RUN_ATTEMPT"))
    args = parser.parse_args()
    if not args.expected_run_id or not args.expected_sha or not args.expected_run_attempt:
        raise SystemExit("render observer ingest failed: expected workflow provenance is required")
    try:
        result = ingest_render_artifact(
            DufyndJarvisBridge(),
            args.artifact,
            expected_run_id=args.expected_run_id,
            expected_sha=args.expected_sha,
            expected_run_attempt=args.expected_run_attempt,
        )
    except ArtifactError as exc:
        raise SystemExit(f"render observer ingest failed: {exc}") from None
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
