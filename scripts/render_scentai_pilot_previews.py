from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from scripts.build_scentai_campaign_link import build_campaign_url

DEFAULT_PLAN = Path("examples/retail/data/scentai_launch_content_plan.json")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_launch_links(plan: dict, *, base_url: str) -> list[dict]:
    campaign_id = str(plan.get("campaign_id") or "").strip()
    channels = plan.get("channels")
    content_rows = plan.get("content")

    if not campaign_id:
        raise ValueError("Launch plan requires campaign_id")
    if not isinstance(channels, list) or not channels:
        raise ValueError("Launch plan requires channels")
    if not isinstance(content_rows, list) or not content_rows:
        raise ValueError("Launch plan requires content rows")

    rows: list[dict] = []
    for content in content_rows:
        content_id = str(content.get("content_id") or "").strip()
        landing_path = str(content.get("landing_path") or "").strip()

        if not content_id or not landing_path:
            raise ValueError("Every content row requires content_id and landing_path")

        for channel in channels:
            link = build_campaign_url(
                base_url=base_url,
                landing_path=landing_path,
                channel=str(channel),
                campaign_id=campaign_id,
                content_id=content_id,
            )
       
…[78197 chars truncated — re-run with head/grep/tail for full output]…
        "release_count": len(release_rows),
        "staged_product_count": len(staged_by_id),
        "release_product_count": len(all_release_product_ids),
        "mapped_staged_product_count": len(mapped_staged_product_ids),
        "unmapped_staged_product_count": (len(staged_by_id) - len(mapped_staged_product_ids)),
        "write_ready_release_count": sum(1 for release in release_rows if release["write_ready"]),
        "releases": release_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Report guarded SCENTAI release-pipeline readiness across all "
            "prepared release manifests."
        )
    )
    parser.add_argument(
        "--staging",
        type=Path,
        default=DEFAULT_STAGING,
    )
    parser.add_argument(
        "--offers",
        type=Path,
        default=DEFAULT_OFFERS,
    )
    parser.add_argument(
        "--mappings",
        type=Path,
        default=DEFAULT_MAPPINGS,
    )
    parser.add_argument(
        "--release-dir",
        type=Path,
        default=DATA_DIR,
    )
    parser.add_argument(
        "--release-pattern",
        default=DEFAULT_RELEASE_GLOB,
    )
    parser.add_argument(
        "--max-offer-age-hours",
        type=float,
        default=72.0,
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    args = parser.parse_args()

    releases = load_release_manifests(
        args.release_dir,
        args.release_pattern,
    )
    report = build_release_pipeline_report(
        releases,
        load_json(args.staging),
        load_json(args.offers),
        load_json(args.mappings),
        now=datetime.now(UTC),
        max_offer_age_hours=args.max_offer_age_hours,
    )

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
        return 0

    print(
        "SCENTAI release pipeline | "
        f"releases={report['release_count']} | "
        f"staged={report['staged_product_count']} | "
        f"mapped={report['mapped_staged_product_count']} | "
        f"write_ready_releases={report['write_ready_release_count']}"
    )

    for release in report["releases"]:
        blockers = ", ".join(release["release_blockers"]) or "-"
        print(
            f"{release['release_id']} | "
            f"mapped={release['mapped_product_count']}/"
            f"{release['product_count']} | "
            f"affiliate={release['affiliate_offer_product_count']}/"
            f"{release['product_count']} | "
            f"ready={release['ready_product_count']}/"
            f"{release['product_count']} | "
            f"write_enabled={release['write_enabled']} | "
            f"blockers={blockers}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
