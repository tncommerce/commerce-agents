from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path

DATA_DIR = Path("examples/retail/data")
DEFAULT_WAVE = DATA_DIR / "dufynd_catalog_expansion_next10.json"
DEFAULT_CATALOG = DATA_DIR / "catalog.json"
DEFAULT_STAGING = DATA_DIR / "scentai_catalog_staging.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def valid_gtin(value: object) -> bool:
    if not isinstance(value, str) or len(value) not in {8, 12, 13, 14}:
        return False
    if not value.isascii() or not value.isdigit():
        return False
    total = sum(
        int(digit) * (3 if index % 2 == 0 else 1)
        for index, digit in enumerate(reversed(value[:-1]))
    )
    return (total + int(value[-1])) % 10 == 0


def validate_research_details(row: dict, prefix: str) -> list[str]:
    errors = []
    community = row.get("community")
    if community is not None:
        for field in ("rating_10", "longevity_10", "projection_10"):
            value = community.get(field)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 10:
                errors.append(f"{prefix}:invalid_{field}")
        for field in ("rating_count", "longevity_count", "projection_count"):
            value = community.get(field)
            if type(value) is not int or value <= 0:
                errors.append(f"{prefix}:invalid_{field}")
        if not str(community.get("source_url") or "").startswith("https://"):
            errors.append(f"{prefix}:invalid_community_source_url")
        try:
            date.fromisoformat(community.get("checked_at", ""))
        except (TypeError, ValueError):
            errors.append(f"{prefix}:invalid_community_checked_at")

    identifiers = row.get("identifiers")
    if identifiers is not None:
        observations = identifiers.get("observations") or []
        status = identifiers.get("status")
        if status not in {
            "pending_primary_variant_verification",
            "source_verified_feed_match_pending",
            "indexed_evidence_feed_match_pending",
        }:
            errors.append(f"{prefix}:invalid_identifier_status")
        if status != "pending_primary_variant_verification" and not observations:
            errors.append(f"{prefix}:missing_identifier_evidence")
        if identifiers.get("canonical_gtin") is not None:
            errors.append(f"{prefix}:canonical_gtin_not_allowed_in_research")
        for index, observation in enumerate(observations, start=1):
            label = f"{prefix}:identifier_{index}"
            if not valid_gtin(observation.get("gtin")):
                errors.append(f"{label}:invalid_gtin")
            if (
                type(observation.get("volume_ml")) is not int
                or observation.get("volume_ml") != row.get("volume_ml")
                or observation.get("concentration") != row.get("concentration")
            ):
                errors.append(f"{label}:variant_mismatch")
            if not str(observation.get("source_url") or "").startswith("https://"):
                errors.append(f"{label}:invalid_source_url")
            if observation.get("evidence_kind") not in {
                "product_page",
                "indexed_merchant_product_page",
            }:
                errors.append(f"{label}:invalid_evidence_kind")
            try:
                date.fromisoformat(observation.get("checked_at", ""))
            except (TypeError, ValueError):
                errors.append(f"{label}:invalid_checked_at")
        if row.get("validation", {}).get("catalog_ready") is not False:
            errors.append(f"{prefix}:research_must_remain_blocked")
        if not row.get("validation", {}).get("blockers"):
            errors.append(f"{prefix}:missing_publication_blockers")
    return errors


def validate_wave(wave: dict, catalog: dict, staging: dict) -> list[str]:
    errors: list[str] = []

    candidates = wave.get("candidates", [])
    candidate_ids = [str(row.get("product_id") or "").strip() for row in candidates]
    nonempty_candidate_ids = [product_id for product_id in candidate_ids if product_id]

    if not candidates:
        errors.append("wave_has_no_candidates")

    if len(set(nonempty_candidate_ids)) != len(nonempty_candidate_ids):
        errors.append("duplicate_candidate_product_id")

    live_ids = {
        str(row.get("product_id") or "").strip()
        for row in catalog.get("products", [])
        if str(row.get("product_id") or "").startswith("SC-")
        and row.get("category") == "fragrance"
        and row.get("in_stock") is not False
    }
    staged_ids = {
        str(row.get("product_id") or "").strip()
        for row in staging.get("products", [])
        if str(row.get("product_id") or "").strip()
    }

    for index, row in enumerate(candidates, start=1):
        prefix = f"candidate_{index}"
        errors.extend(validate_research_details(row, prefix))

        product_id = str(row.get("product_id") or "").strip()
        if not product_id:
            errors.append(f"{prefix}:missing_product_id")
            continue
        if not product_id.startswith("SC-"):
            errors.append(f"{prefix}:invalid_product_id_prefix")
        if product_id in live_ids:
            errors.append(f"{prefix}:already_live:{product_id}")
        if product_id in staged_ids:
            errors.append(f"{prefix}:already_staged:{product_id}")

        if not str(row.get("brand") or "").strip():
            errors.append(f"{prefix}:missing_brand")
        if not str(row.get("name") or "").strip():
            errors.append(f"{prefix}:missing_name")
        if not str(row.get("concentration") or "").strip():
            errors.append(f"{prefix}:missing_concentration")

        volume = row.get("volume_ml")
        if type(volume) is not int or volume <= 0:
            errors.append(f"{prefix}:invalid_volume_ml")

        if row.get("variant_status") != "verified_retail_variant":
            errors.append(f"{prefix}:variant_not_verified")

        evidence = row.get("evidence") or []
        if not evidence:
            errors.append(f"{prefix}:missing_evidence")
        elif not all(str(item.get("url") or "").startswith("https://") for item in evidence):
            errors.append(f"{prefix}:invalid_evidence_url")

        product_data = row.get("product_data")
        if product_data is not None:
            source_url = str(product_data.get("source_url") or "").strip()
            if not source_url.startswith("https://"):
                errors.append(f"{prefix}:invalid_product_data_source_url")
            if not str(product_data.get("source_kind") or "").strip():
                errors.append(f"{prefix}:missing_product_data_source_kind")

            merchant_evidence = row.get("research_merchant_evidence") or []
            if not merchant_evidence:
                errors.append(f"{prefix}:missing_research_merchant_evidence")

            for merchant_index, merchant_row in enumerate(merchant_evidence, start=1):
                merchant_prefix = f"{prefix}:merchant_{merchant_index}"
                if not str(merchant_row.get("merchant") or "").strip():
                    errors.append(f"{merchant_prefix}:missing_merchant")
                if not str(merchant_row.get("url") or "").startswith("https://"):
                    errors.append(f"{merchant_prefix}:invalid_url")
                affiliate_state = str(merchant_row.get("affiliate_state") or "").strip()
                if affiliate_state not in {
                    "application_pending",
                    "cj_application_pending",
                    "not_affiliate_target",
                }:
                    errors.append(f"{merchant_prefix}:invalid_affiliate_state")
                if merchant_row.get("affiliate_url"):
                    errors.append(f"{merchant_prefix}:affiliate_url_not_allowed_in_research")

    enrichment = wave.get("enrichment") or {}
    details = enrichment.get("community_and_identity")
    if details is not None:
        counts = {
            "community_product_count": sum(bool(row.get("community")) for row in candidates),
            "identifier_source_evidence_count": sum(
                bool(row.get("identifiers", {}).get("observations")) for row in candidates
            ),
            "image_queue_count": sum(bool(row.get("media")) for row in candidates),
            "catalog_ready_count": sum(
                row.get("validation", {}).get("catalog_ready") is True for row in candidates
            ),
        }
        for field, actual in counts.items():
            if type(details.get(field)) is not int or details.get(field) != actual:
                errors.append(f"enrichment_{field}_mismatch")
    total_enriched = enrichment.get("total_enriched")
    if total_enriched is not None:
        actual_enriched = sum(1 for row in candidates if row.get("product_data"))
        if total_enriched != actual_enriched:
            errors.append("enrichment_total_mismatch")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a DUFYND catalog expansion candidate queue."
    )
    parser.add_argument("--wave", type=Path, default=DEFAULT_WAVE)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    wave = load_json(args.wave)
    errors = validate_wave(
        wave,
        load_json(args.catalog),
        load_json(args.staging),
    )
    report = {
        "wave_id": wave.get("wave_id"),
        "candidate_count": len(wave.get("candidates", [])),
        "valid": not errors,
        "errors": errors,
    }

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            f"DUFYND catalog wave | id={report['wave_id']} | "
            f"candidates={report['candidate_count']} | valid={report['valid']}"
        )
        for error in errors:
            print(f"  - {error}")

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
