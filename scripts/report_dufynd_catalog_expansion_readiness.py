from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.validate_dufynd_catalog_expansion_wave import validate_wave

DATA_DIR = Path("examples/retail/data")
DEFAULT_WAVE = DATA_DIR / "dufynd_catalog_expansion_next10.json"
DEFAULT_LIVE = DATA_DIR / "catalog.json"
DEFAULT_STAGING = DATA_DIR / "scentai_catalog_staging.json"

STAGING_HARD_BLOCKERS = {
    "direct_source_or_feed_confirmation_pending",
    "full_note_pyramid_conflict_pending",
    "merchant_concentration_attribute_review_pending",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def live_audience_counts(catalog: dict[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()

    for product in catalog.get("products", []):
        if product.get("category") != "fragrance":
            continue
        if product.get("in_stock") is False:
            continue
        if not str(product.get("product_id") or "").startswith("SC-"):
            continue

        raw = str(product.get("attributes", {}).get("target_group") or "")
        counts.update(group.strip() for group in raw.split(",") if group.strip())

    return counts


def audience_gap_score(
    target_groups: list[str],
    live_counts: Counter[str],
) -> float:
    normalized = [str(group).strip() for group in target_groups if str(group).strip()]
    if not normalized:
        return 0.0

    maximum = max(live_counts.values(), default=0)
    if maximum <= 0:
        return 10.0

    lowest = min(int(live_counts.get(group, 0)) for group in normalized)
    return round(min(10.0, max(0.0, (maximum - lowest) / maximum * 10.0)), 2)


def candidate_validation_errors(
    candidate: dict[str, Any],
    live: dict[str, Any],
    staging: dict[str, Any],
) -> list[str]:
    report = {
        "candidates": [candidate],
    }
    return validate_wave(report, live, staging)


def build_expansion_readiness(
    wave: dict[str, Any],
    live: dict[str, Any],
    staging: dict[str, Any],
    *,
    staging_batch_limit: int = 5,
) -> dict[str, Any]:
    if staging_batch_limit < 1:
        raise ValueError("staging_batch_limit must be at least 1")

    live_counts = live_audience_counts(live)
    live_ids = {
        str(product.get("product_id") or "").strip()
        for product in live.get("products", [])
        if str(product.get("product_id") or "").strip()
    }
    staged_ids = {
        str(product.get("product_id") or "").strip()
        for product in staging.get("products", [])
        if str(product.get("product_id") or "").strip()
    }

    rows: list[dict[str, Any]] = []
    staging_blocker_counts: Counter[str] = Counter()
    live_blocker_counts: Counter[str] = Counter()

    for candidate in wave.get("candidates", []):
        product_id = str(candidate.get("product_id") or "").strip()
        validation_errors = candidate_validation_errors(candidate, live, staging)
        declared_live_blockers = list(candidate.get("validation", {}).get("blockers", []) or [])

        staging_blockers = [
            blocker for blocker in declared_live_blockers if blocker in STAGING_HARD_BLOCKERS
        ]
        staging_blockers.extend(validation_errors)

        if product_id in live_ids:
            staging_blockers.append("already_live")
        if product_id in staged_ids:
            staging_blockers.append("already_staged")

        staging_blockers = list(dict.fromkeys(staging_blockers))
        live_blockers = list(dict.fromkeys(declared_live_blockers + validation_errors))

        staging_blocker_counts.update(staging_blockers)
        live_blocker_counts.update(live_blockers)

        merchant_count = len(candidate.get("research_merchant_evidence", []) or [])
        target_groups = [
            str(group).strip()
            for group in candidate.get("target_groups", []) or []
            if str(group).strip()
        ]

        rows.append(
            {
                "priority": candidate.get("priority"),
                "product_id": product_id,
                "brand": candidate.get("brand"),
                "name": candidate.get("name"),
                "concentration": candidate.get("concentration"),
                "volume_ml": candidate.get("volume_ml"),
                "target_groups": target_groups,
                "audience_gap_score_10": audience_gap_score(target_groups, live_counts),
                "researched_merchant_count": merchant_count,
                "research_state": candidate.get("research_state"),
                "staging_ready": not staging_blockers,
                "staging_blockers": staging_blockers,
                "live_ready": bool(candidate.get("validation", {}).get("catalog_ready"))
                and not live_blockers,
                "live_blockers": live_blockers,
            }
        )

    rows.sort(
        key=lambda row: (
            0 if row["staging_ready"] else 1,
            -row["audience_gap_score_10"],
            int(row["priority"] or 999),
            -row["researched_merchant_count"],
            str(row["brand"] or "").casefold(),
            str(row["name"] or "").casefold(),
        )
    )

    recommended = [row for row in rows if row["staging_ready"]][:staging_batch_limit]

    return {
        "wave_id": wave.get("wave_id"),
        "candidate_count": len(rows),
        "live_fragrance_count": sum(
            1
            for product in live.get("products", [])
            if product.get("category") == "fragrance"
            and product.get("in_stock") is not False
            and str(product.get("product_id") or "").startswith("SC-")
        ),
        "staged_product_count": len(staged_ids),
        "live_audience_counts": dict(sorted(live_counts.items())),
        "staging_ready_count": sum(1 for row in rows if row["staging_ready"]),
        "staging_blocked_count": sum(1 for row in rows if not row["staging_ready"]),
        "live_ready_count": sum(1 for row in rows if row["live_ready"]),
        "staging_blocker_counts": dict(
            sorted(staging_blocker_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "live_blocker_counts": dict(
            sorted(live_blocker_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "recommended_staging_batch": recommended,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report DUFYND research-wave readiness for staging and live promotion."
    )
    parser.add_argument("--wave", type=Path, default=DEFAULT_WAVE)
    parser.add_argument("--live", type=Path, default=DEFAULT_LIVE)
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--staging-batch-limit", type=int, default=5)
    parser.add_argument("--machine-readable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    try:
        report = build_expansion_readiness(
            load_json(args.wave),
            load_json(args.live),
            load_json(args.staging),
            staging_batch_limit=args.staging_batch_limit,
        )
    except ValueError as exc:
        parser.error(str(exc))

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
        "DUFYND expansion readiness | "
        f"wave={report['wave_id']} | "
        f"candidates={report['candidate_count']} | "
        f"staging_ready={report['staging_ready_count']} | "
        f"live_ready={report['live_ready_count']}"
    )
    print(
        "Live audiences | "
        + " | ".join(f"{group}={count}" for group, count in report["live_audience_counts"].items())
    )
    print("Recommended staging batch:")
    for index, row in enumerate(report["recommended_staging_batch"], start=1):
        print(
            f"  {index:>2}. {row['product_id']} | "
            f"audience_gap={row['audience_gap_score_10']}/10 | "
            f"merchants={row['researched_merchant_count']}"
        )

    if report["staging_blocker_counts"]:
        print("Staging blockers:")
        for blocker, count in report["staging_blocker_counts"].items():
            print(f"  {count:>2}  {blocker}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
