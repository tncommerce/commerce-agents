from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.refresh_scentai_jarvis_state import (
    OUT_AFFILIATE,
    OUT_FEED,
    OUT_IMAGES,
    OUT_MAPPING,
    OUT_OPERATIONS,
    OUT_PIPELINE,
    OUT_RELEASE,
    load_json,
    refresh_state,
)

OUTPUT_PATHS = {
    "mapping_queue": OUT_MAPPING,
    "affiliate_status": OUT_AFFILIATE,
    "image_queue": OUT_IMAGES,
    "feed_queue": OUT_FEED,
    "release_status": OUT_RELEASE,
    "release_pipeline": OUT_PIPELINE,
    "operations": OUT_OPERATIONS,
}


def compare_state_graph(
    current: dict[str, dict],
    expected: dict[str, dict],
) -> dict[str, Any]:
    missing = sorted(set(expected) - set(current))
    extra = sorted(set(current) - set(expected))
    drifted = sorted(
        key
        for key in set(current) & set(expected)
        if current[key] != expected[key]
    )

    issues = []
    if missing:
        issues.append("missing_state_nodes:" + ",".join(missing))
    if extra:
        issues.append("unexpected_state_nodes:" + ",".join(extra))
    if drifted:
        issues.append("drifted_state_nodes:" + ",".join(drifted))

    return {
        "valid": not issues,
        "issues": issues,
        "missing_nodes": missing,
        "extra_nodes": extra,
        "drifted_nodes": drifted,
    }


def load_current_state() -> dict[str, dict]:
    return {
        key: load_json(path)
        for key, path in OUTPUT_PATHS.items()
    }


def validate_repo_state_graph() -> dict[str, Any]:
    current = load_current_state()
    generated_at = str(
        current.get("operations", {}).get("generated_at") or ""
    ).strip()
    if not generated_at:
        return {
            "valid": False,
            "issues": ["operations_generated_at_missing"],
            "missing_nodes": [],
            "extra_nodes": [],
            "drifted_nodes": [],
        }

    expected = refresh_state(generated_at=generated_at)
    return compare_state_graph(current, expected)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the complete derived SCENTAI Jarvis state graph "
            "against source-of-truth inputs."
        )
    )
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        report = validate_repo_state_graph()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "SCENTAI Jarvis state graph | "
            f"valid={report['valid']} | "
            f"drift={report.get('drifted_nodes', [])}"
        )
        for issue in report["issues"]:
            print(f"  - {issue}")

    return 0 if report["valid"] else 20


if __name__ == "__main__":
    raise SystemExit(main())
