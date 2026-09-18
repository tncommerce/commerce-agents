from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.promote_scentai_catalog import (
    DEFAULT_CATALOG,
    DEFAULT_OFFERS,
    DEFAULT_STAGING,
    eligible_affiliate_offers,
    load_json,
    promotion_blockers,
)


def promotion_tier(product: dict) -> str:
    community = product.get("community", {})
    if community.get("provisional"):
        return "C"

    coverage = int(
        product.get("commerce", {}).get(
            "merchant_coverage_count",
            0,
        )
        or 0
    )

    if coverage >= 2:
        return "A"
    if coverage >= 1:
        return "B"
    return "C"


def build_readiness_report(
    staging: dict,
    catalog: dict,
    offers_payload: dict,
    *,
    now: datetime,
    max_offer_age_hours: float = 72.0,
    allow_provisional: bool = False,
) -> dict:
    staged_products = staging.get("products", [])
    offers = offers_payload.get(
        "offers",
        offers_payload if isinstance(offers_payload, list) else [],
    )
    live_ids = {
        str(product.get("product_id") or "")
        for product in catalog.get("products", [])
    }

    rows: list[dict[str, Any]] = []
    blocker_counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()

    for product in staged_products:
        product_id = str(product.get("product_id") or "").strip()
        blockers = promotion_blockers(
            product,
            offers,
            now=now,
            max_offer_age_hours=max_offer_age_hours,
            allow_provisional=allow_provisional,
        )

        if product_id and product_id in live_ids:
            blockers.append("already_live")

        # Keep output deterministic and avoid double-counting if future
        # gates happen to emit the same blocker more than once.
        blockers = list(dict.fromkeys(blockers))
        blocker_counts.update(blockers)

        tier = promotion_tier(product)
        tier_counts.update([tier])

        eligible = (
            eligible_affiliate_offers(
                offers,
                product_id=product_id,
                now=now,
                max_age_hours=max_offer_age_hours,
            )
            if product_id
            else []
        )

        coverage = int(
            product.get("commerce", {}).get(
                "merchant_coverage_count",
                0,
            )
            or 0
        )

        rows.append(
            {
                "product_id": product_id,
                "candidate_id": product.get("candidate_id"),
                "batch": product.get("batch"),
                "brand": product.get("brand"),
                "name": product.get("name"),
                "tier": tier,
                "merchant_coverage_count": coverage,
                "eligible_affiliate_offers": len(eligible),
                "ready": not blockers,
                "blockers": blockers,
            }
        )

    rows.sort(
        key=lambda row: (
            0 if row["ready"] else 1,
            len(row["blockers"]),
            {"A": 0, "B": 1, "C": 2}.get(row["tier"], 9),
            -row["merchant_coverage_count"],
            str(row["brand"] or "").casefold(),
            str(row["name"] or "").casefold(),
        )
    )

    ready_count = sum(1 for row in rows if row["ready"])

    return {
        "generated_at": now.astimezone(UTC).isoformat(),
        "staged_count": len(rows),
        "ready_count": ready_count,
        "blocked_count": len(rows) - ready_count,
        "tier_counts": {
            tier: tier_counts.get(tier, 0)
            for tier in ("A", "B", "C")
        },
        "blocker_counts": dict(
            sorted(
                blocker_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Report live-promotion readiness for every staged "
            "SCENTAI fragrance."
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
        "--max-offer-age-hours",
        type=float,
        default=72.0,
    )
    parser.add_argument(
        "--allow-provisional",
        action="store_true",
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the full JSON report.",
    )
    args = parser.parse_args()

    report = build_readiness_report(
        load_json(args.staging),
        load_json(args.catalog),
        load_json(args.offers),
        now=datetime.now(UTC),
        max_offer_age_hours=args.max_offer_age_hours,
        allow_provisional=args.allow_provisional,
    )

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
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
        "SCENTAI promotion readiness | "
        f"staged={report['staged_count']} | "
        f"ready={report['ready_count']} | "
        f"blocked={report['blocked_count']}"
    )
    print(
        "Tiers | "
        + " | ".join(
            f"{tier}={count}"
            for tier, count in report["tier_counts"].items()
        )
    )

    if report["blocker_counts"]:
        print("Blockers:")
        for blocker, count in report["blocker_counts"].items():
            print(f"  {count:>2}  {blocker}")

    print("Closest to live:")
    for row in report["rows"][:10]:
        status = "READY" if row["ready"] else "BLOCKED"
        blockers = ", ".join(row["blockers"]) or "-"
        print(
            f"  {status} | Tier {row['tier']} | "
            f"{row['product_id']} | merchants="
            f"{row['merchant_coverage_count']} | "
            f"affiliate_offers={row['eligible_affiliate_offers']} | "
            f"{blockers}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
