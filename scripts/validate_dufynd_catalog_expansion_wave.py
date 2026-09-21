from __future__ import annotations

import argparse
import json
from pathlib import Path

DATA_DIR = Path("examples/retail/data")
DEFAULT_WAVE = DATA_DIR / "dufynd_catalog_expansion_wave_04.json"
DEFAULT_CATALOG = DATA_DIR / "catalog.json"
DEFAULT_STAGING = DATA_DIR / "scentai_catalog_staging.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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
        if not isinstance(volume, int) or volume <= 0:
            errors.append(f"{prefix}:invalid_volume_ml")

        if row.get("variant_status") != "verified_retail_variant":
            errors.append(f"{prefix}:variant_not_verified")

        evidence = row.get("evidence") or []
        if not evidence:
            errors.append(f"{prefix}:missing_evidence")
        elif not all(str(item.get("url") or "").startswith("https://") for item in evidence):
            errors.append(f"{prefix}:invalid_evidence_url")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a DUFYND catalog expansion wave.")
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
