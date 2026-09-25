from __future__ import annotations

import json
from pathlib import Path

from scripts.report_dufynd_catalog_expansion_readiness import build_expansion_readiness

DATA_DIR = Path("examples/retail/data")
OUTPUT = DATA_DIR / "scentai_catalog_staging.json"
INTAKE = DATA_DIR / "dufynd_catalog_staging_intake.json"
LIVE_CATALOG = DATA_DIR / "catalog.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def target_groups(value: str | None) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def merchant_coverage_count(verified: dict, queue_row: dict) -> int:
    """Resolve researched merchant coverage without mixing product editions."""

    if verified.get("merchant_coverage_source") == "verification_snapshot":
        snapshot = verified.get("merchant_snapshot", {})
        if not isinstance(snapshot, dict):
            return 0
        return sum(1 for status in snapshot.values() if status == "available")

    return int(queue_row.get("merchant_coverage_count", 0) or 0)


PROFILE_WEIGHTS = {
    "freshness": {
        "fresh": 3.0,
        "citrus": 3.0,
        "aquatic": 3.0,
        "green": 2.5,
        "fruity": 1.5,
        "floral": 1.0,
        "aromatic": 1.5,
        "white floral": 1.0,
    },
    "sweetness": {
        "sweet": 3.0,
        "gourmand": 3.0,
        "creamy": 2.0,
        "powdery": 1.5,
        "fruity": 1.5,
        "oriental": 1.0,
        "resinous": 0.5,
    },
    "woodiness": {
        "woody": 3.0,
        "leathery": 2.5,
        "smoky": 2.5,
        "resinous": 2.0,
        "oriental": 1.0,
        "spicy": 0.5,
    },
    "spiciness": {
        "spicy": 3.0,
        "oriental": 1.5,
        "woody": 0.5,
        "resinous": 0.5,
    },
}


def recommendation_profile(accords: list[str]) -> dict:
    """Create deterministic internal retrieval scores from verified accords."""

    normalized = {str(accord).strip().casefold() for accord in accords if str(accord).strip()}

    scores = {}
    for axis, weights in PROFILE_WEIGHTS.items():
        value = 2.0 + sum(weight for term, weight in weights.items() if term in normalized)
        scores[axis] = int(round(min(10.0, max(1.0, value))))

    return {
        "scores": scores,
        "source": "deterministic_editorial_mapping_v1",
        "confidence": "medium",
        "customer_facing": False,
    }


def wave_key_notes(candidate: dict) -> list[str]:
    product_data = candidate.get("product_data") or {}
    direct = product_data.get("key_notes") or []
    if direct:
        return list(dict.fromkeys(str(note).strip() for note in direct if str(note).strip()))

    pyramid = product_data.get("notes") or {}
    notes: list[str] = []
    for stage in ("top", "heart", "base"):
        for note in pyramid.get(stage, []) or []:
            normalized = str(note).strip()
            if normalized and normalized not in notes:
                notes.append(normalized)
    return notes


def wave_staging_row(candidate: dict, *, wave_id: str, batch: int) -> dict:
    community = candidate.get("community") or {}
    accords = list(community.get("main_accords") or [])
    profile = candidate.get("recommendation_profile") or recommendation_profile(accords)
    product_data = candidate.get("product_data") or {}

    return {
        "candidate_id": str(candidate["product_id"]).removeprefix("SC-"),
        "product_id": candidate["product_id"],
        "batch": batch,
        "brand": candidate["brand"],
        "name": candidate["name"],
        "concentration": candidate["concentration"],
        "volume_ml": candidate["volume_ml"],
        "classification": {
            "target_groups": list(candidate.get("target_groups") or []),
            "audience_lean": candidate.get("audience_lean"),
        },
        "fragrance_profile": {
            "scent_family": product_data.get("scent_family"),
            "key_notes": wave_key_notes(candidate),
            "community_accords": accords,
            "recommendation_profile": profile,
        },
        "community": {
            "source": community.get("source") or "Parfumo",
            "rating_10": community.get("rating_10"),
            "rating_count": community.get("rating_count"),
            "longevity_10": community.get("longevity_10"),
            "projection_10": community.get("projection_10"),
            "provisional": bool(community.get("provisional")),
        },
        "media": {
            "image_url": None,
            "image_status": "pending_approved_feed_or_manufacturer_image",
        },
        "commerce": {
            "merchant_coverage_count": len(candidate.get("research_merchant_evidence") or []),
            "merchant_coverage_source": "dufynd_research_wave",
            "market_status": "researched_not_integrated",
            "live_offer_status": "pending_affiliate_approval_or_feed",
        },
        "validation": {
            "catalog_ready": False,
            "blockers": list(candidate.get("validation", {}).get("blockers") or []),
        },
        "research": {
            "source_wave_id": wave_id,
            "research_state": candidate.get("research_state"),
            "evidence_urls": [
                item["url"]
                for item in candidate.get("evidence", []) or []
                if str(item.get("url") or "").startswith("https://")
            ],
        },
    }


def append_enabled_research_waves(
    products: list[dict],
    seen_product_ids: set[str],
) -> None:
    intake = load_json(INTAKE)
    live_catalog = load_json(LIVE_CATALOG)
    default_limit = int(intake.get("default_max_products_per_wave", 5) or 5)

    for config in intake.get("waves", []):
        if config.get("enabled") is not True:
            continue
        if config.get("live_publication_authorized") is not False:
            raise ValueError("Staging intake may not authorize live publication")

        wave_path = DATA_DIR / str(config["source_file"])
        wave = load_json(wave_path)
        expected_wave_id = str(config["wave_id"])
        if wave.get("wave_id") != expected_wave_id:
            raise ValueError(
                f"Wave ID mismatch for {wave_path.name}: "
                f"{wave.get('wave_id')} != {expected_wave_id}"
            )

        limit = int(config.get("max_products", default_limit) or default_limit)
        report = build_expansion_readiness(
            wave,
            live_catalog,
            {"products": products},
            staging_batch_limit=limit,
        )
        candidate_by_id = {
            str(candidate.get("product_id") or ""): candidate
            for candidate in wave.get("candidates", [])
        }
        rows_by_id = {row["product_id"]: row for row in report["rows"]}

        selected_ids = [
            str(product_id).strip()
            for product_id in config.get("selected_product_ids", [])
            if str(product_id).strip()
        ]
        if selected_ids:
            if len(selected_ids) != len(set(selected_ids)):
                raise ValueError(f"Duplicate selected product_id in {expected_wave_id}")
            if len(selected_ids) > limit:
                raise ValueError(
                    f"Selected product count exceeds max_products for {expected_wave_id}"
                )

            selected_rows = []
            for product_id in selected_ids:
                row = rows_by_id.get(product_id)
                if row is None:
                    raise ValueError(
                        f"Unknown selected product_id {product_id} in {expected_wave_id}"
                    )
                if not row["staging_ready"]:
                    raise ValueError(
                        f"Selected product is not staging-ready: {product_id}: "
                        + ", ".join(row["staging_blockers"])
                    )
                selected_rows.append(row)
        else:
            selected_rows = report["recommended_staging_batch"]

        for row in selected_rows:
            product_id = row["product_id"]
            if product_id in seen_product_ids:
                raise ValueError(f"Duplicate staged product_id: {product_id}")

            candidate = candidate_by_id[product_id]
            products.append(
                wave_staging_row(
                    candidate,
                    wave_id=expected_wave_id,
                    batch=int(config["staging_batch"]),
                )
            )
            seen_product_ids.add(product_id)


def main() -> int:
    queue = load_json(DATA_DIR / "scentai_catalog_promotion_queue.json")
    queue_by_id = {row["candidate_id"]: row for row in queue["candidates"]}

    products: list[dict] = []
    seen_product_ids: set[str] = set()

    for batch in (1, 2, 3):
        verification = load_json(DATA_DIR / f"scentai_catalog_batch{batch}_verification.json")
        scent = load_json(DATA_DIR / f"scentai_catalog_batch{batch}_scent_qa.json")
        scent_by_id = {row["candidate_id"]: row for row in scent["products"]}

        for verified in verification["products"]:
            candidate_id = verified["candidate_id"]
            community_row = scent_by_id.get(candidate_id, {})
            community = community_row.get("parfumo", community_row)
            queue_row = queue_by_id[candidate_id]
            product_id = verified["proposed_product_id"]

            if product_id in seen_product_ids:
                raise ValueError(f"Duplicate staged product_id: {product_id}")
            seen_product_ids.add(product_id)

            trend = community.get("trend_snapshot") or {}

            products.append(
                {
                    "candidate_id": candidate_id,
                    "product_id": product_id,
                    "batch": batch,
                    "brand": verified["brand"],
                    "name": verified["canonical_name"],
                    "concentration": verified["concentration"],
                    "volume_ml": verified["canonical_volume_ml"],
                    "classification": {
                        "target_groups": target_groups(verified.get("target_group")),
                        "audience_lean": verified.get("audience_lean"),
                    },
                    "fragrance_profile": {
                        "scent_family": verified.get("scent_family"),
                        "key_notes": verified.get("key_notes", []),
                        "community_accords": community.get("main_accords", []),
                        "recommendation_profile": recommendation_profile(
                            community.get("main_accords", [])
                        ),
                    },
                    "community": {
                        "source": "Parfumo",
                        "rating_10": community.get(
                            "scent_rating_10",
                            trend.get("parfumo_weekly_rating_10"),
                        ),
                        "rating_count": community.get(
                            "scent_ratings_count",
                            trend.get("weekly_ratings_count"),
                        ),
                        "longevity_10": community.get("longevity_10"),
                        "projection_10": community.get("sillage_10"),
                        "provisional": bool(
                            community.get("fast_track")
                            or (
                                community.get("longevity_10") is None
                                and community.get("sillage_10") is None
                            )
                        ),
                    },
                    "media": {
                        "image_url": None,
                        "image_status": "pending_approved_feed_or_manufacturer_image",
                    },
                    "commerce": {
                        "merchant_coverage_count": merchant_coverage_count(
                            verified,
                            queue_row,
                        ),
                        "merchant_coverage_source": verified.get(
                            "merchant_coverage_source",
                            "promotion_queue",
                        ),
                        "market_status": verified.get("market_status"),
                        "live_offer_status": "pending_affiliate_approval_or_feed",
                    },
                    "validation": {
                        "catalog_ready": False,
                        "blockers": queue_row.get("blockers", []),
                    },
                }
            )

    append_enabled_research_waves(products, seen_product_ids)

    products.sort(key=lambda row: (int(row.get("batch") or 999), row["product_id"]))

    payload = {
        "schema_version": "1.0",
        "status": "staging_only_not_loaded_by_live_storefront",
        "product_count": len(products),
        "note": (
            "Canonical pre-live records for verified expansion candidates. "
            "No guessed prices, identifiers, affiliate URLs or product images."
        ),
        "products": products,
    }

    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Staged {len(products)} verified DUFYND products -> {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
