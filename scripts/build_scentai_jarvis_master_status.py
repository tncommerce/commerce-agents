from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_COMMERCE = DATA_DIR / "scentai_jarvis_operations_status.json"
DEFAULT_CONTENT = DATA_DIR / "scentai_content_operations_status.json"
DEFAULT_RELEASE_PIPELINE = DATA_DIR / "scentai_release_pipeline_status.json"
DEFAULT_OUTPUT = DATA_DIR / "scentai_jarvis_master_status.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def source_fingerprint(*payloads: object) -> str:
    digest = hashlib.sha256()
    for payload in payloads:
        digest.update(canonical_bytes(payload))
    return digest.hexdigest()


def classify_domain(
    *,
    name: str,
    status: dict,
) -> dict[str, Any]:
    next_action = str(status.get("next_action") or "").strip()
    action_class = str(status.get("next_action_class") or "").strip()
    approval_now = bool(status.get("user_approval_required_now"))

    external_wait_actions = {
        "await_affiliate_program_decision",
        "await_external_dependency",
    }

    if approval_now:
        execution_state = "user_approval_required"
    elif next_action in external_wait_actions:
        execution_state = "waiting_external"
    elif action_class == "auto_allowed" and next_action:
        execution_state = "work_available"
    elif next_action:
        execution_state = "manual_step_pending"
    else:
        execution_state = "idle"

    return {
        "domain": name,
        "overall_state": status.get("overall_state"),
        "execution_state": execution_state,
        "next_action": next_action or None,
        "next_action_class": action_class or None,
        "user_approval_required_now": approval_now,
        "blockers": list(status.get("blockers", [])),
    }


def build_master_status(
    commerce: dict,
    content: dict,
    release_pipeline: dict,
    *,
    generated_at: str,
    content_pipeline: dict | None = None,
) -> dict[str, Any]:
    domains = [
        classify_domain(name="commerce", status=commerce),
        classify_domain(name="content", status=content),
    ]

    approval_domains = [
        row for row in domains if row["execution_state"] == "user_approval_required"
    ]
    work_domains = [row for row in domains if row["execution_state"] == "work_available"]
    manual_domains = [row for row in domains if row["execution_state"] == "manual_step_pending"]

    if approval_domains:
        selected = approval_domains[0]
        overall_state = "user_approval_required"
    elif work_domains:
        selected = work_domains[0]
        overall_state = "work_available"
    elif manual_domains:
        selected = manual_domains[0]
        overall_state = "manual_step_pending"
    else:
        selected = domains[0] if domains else None
        overall_state = "waiting_external_or_idle"

    return {
        "version": 1,
        "generated_at": generated_at,
        "source_fingerprint_sha256": source_fingerprint(
            commerce,
            content,
            release_pipeline,
            *([content_pipeline] if content_pipeline is not None else []),
        ),
        "system": "SCENTAI",
        "control_plane": "commerce_jarvis_master",
        "overall_state": overall_state,
        "active_domain": (selected.get("domain") if selected else None),
        "next_action": (selected.get("next_action") if selected else None),
        "next_action_class": (selected.get("next_action_class") if selected else None),
        "user_approval_required_now": bool(selected and selected.get("user_approval_required_now")),
        "domains": {row["domain"]: row for row in domains},
        "release_pipeline": {
            "release_count": release_pipeline.get("release_count"),
            "current_release_id": release_pipeline.get("current_release_id"),
            "pipeline_state": release_pipeline.get("pipeline_state"),
        },
        "content_pipeline": (
            {
                "batch_count": content_pipeline.get("batch_count"),
                "total_pilots": content_pipeline.get("total_pilots"),
                "current_batch_id": content_pipeline.get("current_batch_id"),
                "pipeline_state": content_pipeline.get("pipeline_state"),
                "production_parallel_allowed": content_pipeline.get("production_parallel_allowed"),
            }
            if content_pipeline is not None
            else None
        ),
        "safety": {
            "automatic_spend_allowed": False,
            "automatic_live_catalog_release_allowed": False,
            "automatic_social_publish_allowed": False,
            "secrets_allowed_in_repo_state": False,
            "high_impact_actions_require_user_approval": True,
        },
        "operating_rule": (
            "Jarvis may continue non-destructive auto_allowed work in the "
            "selected domain while other domains wait on external events. "
            "High-impact or publish/live actions always stop at user approval."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=("Build the cross-domain SCENTAI Jarvis master operations status.")
    )
    parser.add_argument(
        "--commerce",
        type=Path,
        default=DEFAULT_COMMERCE,
    )
    parser.add_argument(
        "--content",
        type=Path,
        default=DEFAULT_CONTENT,
    )
    parser.add_argument(
        "--release-pipeline",
        type=Path,
        default=DEFAULT_RELEASE_PIPELINE,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    generated_at = args.generated_at or datetime.now(UTC).replace(microsecond=0).isoformat()

    report = build_master_status(
        load_json(args.commerce),
        load_json(args.content),
        load_json(args.release_pipeline),
        generated_at=generated_at,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "SCENTAI Jarvis master | "
            f"state={report['overall_state']} | "
            f"domain={report['active_domain']} | "
            f"next={report['next_action']} | "
            f"approval_now={report['user_approval_required_now']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
