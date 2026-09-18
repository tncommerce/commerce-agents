from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.promote_scentai_catalog import promotion_blockers

DATA_DIR = Path("examples/retail/data")
DEFAULT_STAGING = DATA_DIR / "scentai_catalog_staging.json"
DEFAULT_CATALOG = DATA_DIR / "catalog.json"
DEFAULT_OFFERS = DATA_DIR / "merchant_offers.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def live_target_counts(catalog: dict) -> Counter:
    counts: Counter = Counter()

    for product in catalog.get("products", []):
        if not str(product.get("product_id") or "").startswith("SC-"):
            continue
        if product.get("category") != "fragrance":
            continue
        if product.get("in_stock") is False:
            continue

        raw = str(product.get("attributes", {}).get("target_group") or "")
        counts.update(group.strip() for group in raw.split(",") if group.strip())

    return counts


def audience_gap_score(
    target_groups: list[str],
    live_counts: Counter,
) -> float:
    if not target_groups:
        return 0.0

    known_counts = [int(live_counts.get(group, 0)) for group in target_groups]
    if not known_counts:
        return 0.0

    max_live = max([int(value) for value in live_counts.values()] or [0])
    if max_live <= 0:
        return 10.0

    lowest_coverage = min(known_counts)
    gap = max(max_live - lowest_coverage, 0)

    return round(
        min(10.0, (gap / max_live) * 10.0),
        2,
    )


def build_batch_plan(
    staging: dict,
    catalog: dict,
    offers_payload: dict,
    *,
    now: datetime,
    limit: int = 10,
    max_offer_age_hours: float = 72.0,
) -> dict[str, Any]:
    if limit < 1 or limit > 10:
        raise ValueError("limit must be between 1 and 10")

    staged_products = staging.get("products", [])
    offers = offers_payload.get(
        "offers",
        offers_payload if isinstance(offers_payload, list) else [],
    )

    live_ids = {product.get("product_id") for product in catalog.get("products", [])}
    live_counts = live_target_counts(catalog)

    rows: list[dict[str, Any]] = []

    for product in staged_products:
        product_id = str(product.get("product_id") or "").strip()
        if not product_id or product_id in live_ids:
            continue

        blockers = promotion_blockers(
            product,
            offers,
            now=now,
            max_offer_age_hours=max_offer_age_hours,
        )

        target_groups = (
            product.get("classification", {}).get(
                "target_groups",
                [],
            )
            or []
        )
        gap_score = audience_gap_score(
            target_groups,
            live_counts,
        )

        rating_count = int(
            product.get("community", {}).get(
                "rating_count",
                0,
            )
            or 0
        )
        merchant_coverage = int(
            product.get("commerce", {}).get(
                "merchant_coverage_count",
                0,
            )
            or 0
        )
        provisional = bool(product.get("community", {}).get("provisional"))

        rows.append(
            {
                "product_id": product_id,
                "candidate_id": product.get("candidate_id"),
                "batch": product.get("batch"),
                "brand": product.get("brand"),
                "name": product.get("name"),
                "concentration": product.get("concentration"),
                "volume_ml": product.get("volume_ml"),
                "target_groups": target_groups,
                "audience_gap_score_10": gap_score,
                "merchant_coverage_count": merchant_coverage,
                "community_rating_count": rating_count,
                "provisional_community_data": provisional,
                "promotion_ready": not blockers,
                "blockers": blockers,
            }
        )

    rows.sort(
        key=lambda row: (
            0 if row["promotion_ready"] else 1,
            1 if row["provisional_community_data"] else 0,
            len(row["blockers"]),
            -row["audience_gap_score_10"],
            -row["merchant_coverage_count"],
            -row["community_rating_count"],
            int(row["batch"] or 999),
            str(row["brand"] or "").casefold(),
            str(row["name"] or "").casefold(),
        )
    )

    selected = rows[:limit]

    return {
        "generated_at": now.astimezone(UTC).isoformat(),
        "limit": limit,
        "live_audience_counts": dict(sorted(live_counts.items())),
        "selected_count": len(selected),
        "ready_count": sum(1 for row in selected if row["promotion_ready"]),
        "blocked_count": sum(1 for row in selected if not row["promotion_ready"]),
        "selection_rule": (
            "ready first; non-provisional before provisional; "
            "fewer blockers; underrepresented live audiences; "
            "researched merchant coverage; community sample size"
        ),
        "selected": selected,
        "all_rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Plan the next small SCENTAI promotion work batch without bypassing promotion blockers."
        )
    )
    parser.add_argument(
        "--staging",
        type=Path,
        default=DEFAULT_STAGING,
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
    )
    parser.add_argument(
        "--offers",
        type=Path,
        default=DEFAULT_OFFERS,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--max-offer-age-hours",
        type=float,
        default=72.0,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    args = parser.parse_args()

    try:
        report = build_batch_plan(
            load_json(args.staging),
            load_json(args.catalog),
            load_json(args.offers),
            now=datetime.now(UTC),
            limit=args.limit,
            max_offer_age_hours=args.max_offer_age_hours,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if args.output is not None:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        args.output.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
        return 0

    print(
        "SCENTAI next promotion batch | "
        f"selected={report['selected_count']} | "
        f"ready={report['ready_count']} | "
        f"blocked={report['blocked_count']}"
    )
    print(
        "Live audience | "
        + " | ".join(f"{key}={value}" for key, value in report["live_audience_counts"].items())
    )

    for index, row in enumerate(
        report["selected"],
        start=1,
    ):
        blockers = ", ".join(row["blockers"]) or "-"
        print(
            f"  {index:>2}. {row['product_id']} | "
            f"audience_gap="
            f"{row['audience_gap_score_10']}/10 | "
            f"researched_merchants="
            f"{row['merchant_coverage_count']} | "
            f"community_n="
            f"{row['community_rating_count']} | "
            f"blockers={blockers}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
