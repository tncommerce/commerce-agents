from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_BATCH01 = DATA_DIR / "scentai_content_operations_status.json"
DEFAULT_BATCH02 = DATA_DIR / "scentai_content_operations_status_batch02.json"
DEFAULT_OUTPUT = DATA_DIR / "scentai_content_pipeline_status.json"


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


def build_content_pipeline_status(
    batches: list[dict],
    *,
    generated_at: str,
    strategy: dict | None = None,
) -> dict[str, Any]:
    rows = []
    for index, status in enumerate(batches, start=1):
        batch_id = (
            "pilot_batch_01"
            if index == 1
            else "pilot_batch_02"
            if index == 2
            else f"pilot_batch_{index:02d}"
        )
        summary = status.get("summary", {})
        rows.append(
            {
                "batch_id": batch_id,
                "production_order": index,
                "campaign_id": status.get("campaign_id"),
                "overall_state": status.get("overall_state"),
                "next_action": status.get("next_action"),
                "next_action_class": status.get("next_action_class"),
                "user_approval_required_now": bool(status.get("user_approval_required_now")),
                "blockers": list(status.get("blockers", [])),
                "summary": summary,
            }
        )

    legacy_hold = bool(
        strategy
        and strategy.get("active_track") == "high_end_rnd"
        and strategy.get("legacy_pilot_batches") == "hold"
    )

    current = (
        None
        if legacy_hold
        else next(
            (
                row
                for row in rows
                if int(
                    row.get("summary", {}).get(
                        "final_video_renders_ready",
                        0,
                    )
                    or 0
                )
                < int(row.get("summary", {}).get("pilots", 0) or 0)
            ),
            rows[-1] if rows else None,
        )
    )

    total_pilots = sum(int(row.get("summary", {}).get("pilots", 0) or 0) for row in rows)

    pipeline_state = (
        "legacy_batches_on_hold_for_high_end_rnd"
        if legacy_hold
        else "production_work_available"
        if current is not None
        else "no_content_batches"
    )
    strategy_next_action = str(strategy.get("next_action") or "").strip() if strategy else ""
    strategy_next_action_class = (
        str(strategy.get("next_action_class") or "").strip() if strategy else ""
    )
    strategy_approval_now = bool(strategy and strategy.get("user_approval_required_now"))

    return {
        "version": 1,
        "generated_at": generated_at,
        "source_fingerprint_sha256": source_fingerprint(*batches),
        "system": "DUFYND",
        "domain": "content",
        "pipeline_id": "launch_content_pipeline_v1",
        "batch_count": len(rows),
        "total_pilots": total_pilots,
        "current_batch_id": (current.get("batch_id") if current else None),
        "pipeline_state": pipeline_state,
        "active_track": (strategy.get("active_track") if strategy else "legacy_pilot_production"),
        "legacy_pilot_batches": (strategy.get("legacy_pilot_batches") if strategy else "active"),
        "next_action": (
            strategy_next_action
            if legacy_hold and strategy_next_action
            else current.get("next_action")
            if current
            else None
        ),
        "next_action_class": (
            strategy_next_action_class
            if legacy_hold and strategy_next_action_class
            else current.get("next_action_class")
            if current
            else None
        ),
        "user_approval_required_now": (
            strategy_approval_now
            if legacy_hold
            else bool(current and current.get("user_approval_required_now"))
        ),
        "production_parallel_allowed": not legacy_hold,
        "publish_order": [row["batch_id"] for row in rows],
        "totals": {
            "tracked_links_ready": sum(
                int(
                    row.get("summary", {}).get(
                        "tracked_links_ready",
                        0,
                    )
                    or 0
                )
                for row in rows
            ),
            "social_copy_ready": sum(
                int(
                    row.get("summary", {}).get(
                        "social_copy_ready",
                        0,
                    )
                    or 0
                )
                for row in rows
            ),
            "visual_preview_mp4s_ready": sum(
                int(
                    row.get("summary", {}).get(
                        "visual_preview_mp4s_ready",
                        0,
                    )
                    or 0
                )
                for row in rows
            ),
            "final_video_renders_ready": sum(
                int(
                    row.get("summary", {}).get(
                        "final_video_renders_ready",
                        0,
                    )
                    or 0
                )
                for row in rows
            ),
        },
        "batches": rows,
        "operating_rule": (
            "Legacy pilot previews remain available as references and utility "
            "prototypes. When the high-end R&D track is active and legacy batches "
            "are on hold, Jarvis must not request voiceover or final-render work "
            "for those legacy batches. Publish and paid-generation actions remain "
            "explicit user approval gates."
            if legacy_hold
            else (
                "Jarvis may prepare batches in parallel, but publish decisions "
                "remain explicit user approval gates and the declared publish "
                "order is preserved unless the user changes it."
            )
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build DUFYND multi-batch content pipeline status."
    )
    parser.add_argument(
        "--batch-status",
        action="append",
        type=Path,
        default=None,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    paths = args.batch_status or [
        DEFAULT_BATCH01,
        DEFAULT_BATCH02,
    ]
    generated_at = args.generated_at or datetime.now(UTC).replace(microsecond=0).isoformat()

    report = build_content_pipeline_status(
        [load_json(path) for path in paths],
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
            "DUFYND content pipeline | "
            f"batches={report['batch_count']} | "
            f"pilots={report['total_pilots']} | "
            f"current={report['current_batch_id']} | "
            f"state={report['pipeline_state']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
