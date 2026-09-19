from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.build_scentai_content_operations_status import (
    build_content_operations_status,
)
from scripts.build_scentai_content_pipeline_status import (
    build_content_pipeline_status,
)
from scripts.build_scentai_image_approval_work_queue import (
    build_queue as build_image_queue,
)
from scripts.build_scentai_jarvis_master_status import (
    build_master_status,
)
from scripts.build_scentai_jarvis_operations_status import (
    build_operations_status,
)
from scripts.build_scentai_merchant_mapping_work_queue import (
    build_queue as build_mapping_queue,
)
from scripts.build_scentai_release_feed_activation_queue import (
    build_feed_activation_queue,
)
from scripts.build_scentai_release_gate_status import (
    build_release_gate_status,
)
from scripts.build_scentai_release_pipeline_status import (
    build_release_pipeline_status,
)
from scripts.evaluate_scentai_affiliate_activation import (
    build_state_report,
)

DATA_DIR = Path("examples/retail/data")

STAGING = DATA_DIR / "scentai_catalog_staging.json"
MAPPINGS = DATA_DIR / "merchant_product_mappings.json"
AFFILIATES = DATA_DIR / "scentai_affiliate_programs.json"
OFFERS = DATA_DIR / "merchant_offers.json"
RELEASE_01 = DATA_DIR / "scentai_release_batch_01.json"
RELEASE_02 = DATA_DIR / "scentai_release_batch_02.json"
RELEASE_03 = DATA_DIR / "scentai_release_batch_03.json"
ASSET_CANDIDATES = DATA_DIR / "scentai_image_asset_candidates.json"
PILOT_MANIFEST = DATA_DIR / "scentai_pilot_batch_01.json"
PILOT_READINESS = DATA_DIR / "scentai_pilot_batch_01_readiness.json"
PILOT_JOBS = DATA_DIR / "scentai_pilot_batch_01_production_jobs.json"
PILOT_SUBTITLES = DATA_DIR / "scentai_pilot_batch_01_subtitles.json"
PILOT_LINKS = DATA_DIR / "scentai_pilot_batch_01_links.json"
PILOT_SOCIAL_COPY = DATA_DIR / "scentai_pilot_batch_01_social_copy.json"
PILOT2_MANIFEST = DATA_DIR / "scentai_pilot_batch_02.json"
PILOT2_READINESS = DATA_DIR / "scentai_pilot_batch_02_readiness.json"
PILOT2_JOBS = DATA_DIR / "scentai_pilot_batch_02_production_jobs.json"
PILOT2_SUBTITLES = DATA_DIR / "scentai_pilot_batch_02_subtitles.json"
PILOT2_LINKS = DATA_DIR / "scentai_pilot_batch_02_links.json"
PILOT2_SOCIAL_COPY = DATA_DIR / "scentai_pilot_batch_02_social_copy.json"

OUT_MAPPING = DATA_DIR / "scentai_merchant_mapping_work_queue.json"
OUT_AFFILIATE = DATA_DIR / "scentai_affiliate_activation_status.json"
OUT_IMAGES = DATA_DIR / "scentai_image_approval_work_queue.json"
OUT_FEED = DATA_DIR / "scentai_release_01_feed_activation_queue.json"
OUT_RELEASE = DATA_DIR / "scentai_release_01_gate_status.json"
OUT_PIPELINE = DATA_DIR / "scentai_release_pipeline_status.json"
OUT_OPERATIONS = DATA_DIR / "scentai_jarvis_operations_status.json"
OUT_CONTENT = DATA_DIR / "scentai_content_operations_status.json"
OUT_CONTENT_BATCH02 = (
    DATA_DIR / "scentai_content_operations_status_batch02.json"
)
OUT_CONTENT_PIPELINE = DATA_DIR / "scentai_content_pipeline_status.json"
OUT_MASTER = DATA_DIR / "scentai_jarvis_master_status.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def refresh_state(*, generated_at: str) -> dict[str, Any]:
    staging = load_json(STAGING)
    mappings = load_json(MAPPINGS)
    affiliates = load_json(AFFILIATES)
    offers = load_json(OFFERS)
    release_01 = load_json(RELEASE_01)
    releases = [
        release_01,
        load_json(RELEASE_02),
        load_json(RELEASE_03),
    ]

    mapping_queue = build_mapping_queue(
        staging,
        mappings,
        affiliates,
        generated_at=generated_at,
    )
    affiliate_status = build_state_report(
        affiliates,
        generated_at=generated_at,
    )
    image_queue = build_image_queue(
        staging,
        releases,
        generated_at=generated_at,
        asset_candidates=(
            load_json(ASSET_CANDIDATES)
            if ASSET_CANDIDATES.exists()
            else None
        ),
    )
    feed_queue = build_feed_activation_queue(
        release_01,
        mappings,
        affiliates,
        generated_at=generated_at,
    )
    release_status = build_release_gate_status(
        release_01,
        staging,
        mappings,
        offers,
        image_queue,
        affiliate_status,
        generated_at=generated_at,
    )
    release_pipeline = build_release_pipeline_status(
        releases,
        staging,
        mappings,
        offers,
        image_queue,
        affiliate_status,
        generated_at=generated_at,
    )
    operations = build_operations_status(
        mapping_queue,
        affiliate_status,
        image_queue,
        release_status,
        feed_queue,
        generated_at=generated_at,
    )
    content_status = build_content_operations_status(
        load_json(PILOT_MANIFEST),
        load_json(PILOT_READINESS),
        load_json(PILOT_JOBS),
        load_json(PILOT_SUBTITLES),
        load_json(PILOT_LINKS),
        load_json(PILOT_SOCIAL_COPY),
        generated_at=generated_at,
    )
    content_status_batch02 = build_content_operations_status(
        load_json(PILOT2_MANIFEST),
        load_json(PILOT2_READINESS),
        load_json(PILOT2_JOBS),
        load_json(PILOT2_SUBTITLES),
        load_json(PILOT2_LINKS),
        load_json(PILOT2_SOCIAL_COPY),
        generated_at=generated_at,
    )
    content_status_batch02["batch_id"] = "pilot_batch_02"

    content_pipeline = build_content_pipeline_status(
        [content_status, content_status_batch02],
        generated_at=generated_at,
    )

    master_status = build_master_status(
        operations,
        content_status,
        release_pipeline,
        generated_at=generated_at,
        content_pipeline=content_pipeline,
    )

    return {
        "mapping_queue": mapping_queue,
        "affiliate_status": affiliate_status,
        "image_queue": image_queue,
        "feed_queue": feed_queue,
        "release_status": release_status,
        "release_pipeline": release_pipeline,
        "operations": operations,
        "content_status": content_status,
        "content_status_batch02": content_status_batch02,
        "content_pipeline": content_pipeline,
        "master_status": master_status,
    }


def write_state(state: dict[str, Any]) -> None:
    write_json(OUT_MAPPING, state["mapping_queue"])
    write_json(OUT_AFFILIATE, state["affiliate_status"])
    write_json(OUT_IMAGES, state["image_queue"])
    write_json(OUT_FEED, state["feed_queue"])
    write_json(OUT_RELEASE, state["release_status"])
    write_json(OUT_PIPELINE, state["release_pipeline"])
    write_json(OUT_OPERATIONS, state["operations"])
    write_json(OUT_CONTENT, state["content_status"])
    write_json(
        OUT_CONTENT_BATCH02,
        state["content_status_batch02"],
    )
    write_json(
        OUT_CONTENT_PIPELINE,
        state["content_pipeline"],
    )
    write_json(OUT_MASTER, state["master_status"])


def summary(state: dict[str, Any]) -> dict[str, Any]:
    master = state["master_status"]
    return {
        "overall_state": master["overall_state"],
        "active_domain": master["active_domain"],
        "next_action": master["next_action"],
        "user_approval_required_now": master[
            "user_approval_required_now"
        ],
        "mapping": state["mapping_queue"]["summary"],
        "affiliate": state["affiliate_status"]["summary"],
        "images": state["image_queue"]["summary"],
        "feed": state["feed_queue"]["summary"],
        "release_01": state["release_status"]["summary"],
        "release_pipeline": {
            "release_count": state["release_pipeline"]["release_count"],
            "current_release_id": state["release_pipeline"][
                "current_release_id"
            ],
            "pipeline_state": state["release_pipeline"]["pipeline_state"],
        },
        "content": state["content_status"]["summary"],
        "content_pipeline": {
            "batch_count": state["content_pipeline"]["batch_count"],
            "total_pilots": state["content_pipeline"]["total_pilots"],
            "current_batch_id": state["content_pipeline"][
                "current_batch_id"
            ],
            "pipeline_state": state["content_pipeline"][
                "pipeline_state"
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild all derived SCENTAI Jarvis operational views in "
            "dependency order from source-of-truth data. Dry-run by default."
        )
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    generated_at = (
        args.generated_at
        or datetime.now(UTC).replace(microsecond=0).isoformat()
    )

    state = refresh_state(generated_at=generated_at)
    if args.write:
        write_state(state)

    report = {
        "dry_run": not args.write,
        "wrote": bool(args.write),
        "generated_at": generated_at,
        "summary": summary(state),
        "live_catalog_modified": False,
        "affiliate_routing_modified": False,
        "money_spent": False,
        "outbound_message_sent": False,
    }

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        ops = report["summary"]
        print(
            "SCENTAI Jarvis state refresh | "
            f"dry_run={report['dry_run']} | "
            f"state={ops['overall_state']} | "
            f"domain={ops['active_domain']} | "
            f"next={ops['next_action']} | "
            f"approval_now={ops['user_approval_required_now']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
