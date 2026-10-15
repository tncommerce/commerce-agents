"""Bounded offline manufacturer review. Never invokes staging or public exporters.

This is a private preparation contract, not a catalog row or release authorization.
The only accepted input is the three source-qualified GROWTH-02 records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/dufynd-growth-02-import-hold.json"
INPUT_SHA256 = "66b7e32c9415232b71fd2d7fac379a522be080386b5734143bc8843f3e54b76f"
SOURCE_COMMIT = "8647495e5619d1acfaa1346949d586e3b27c4fab"
REGISTRIES = ("catalog.json", "scentai_products.json", "scentai_catalog_staging.json")
IDENTITIES = {
    "BDK-GRIS-CHARNEL-EDP": ("SC-BDK-GRIS-CHARNEL-EDP-100", "BDK Parfums", "Gris Charnel", 100),
    "MONTALE-ARABIANS-TONKA-EDP": (
        "SC-MONTALE-ARABIANS-TONKA-EDP-100",
        "Montale",
        "Arabians Tonka",
        100,
    ),
    "PDM-VALAYA-EDP": ("SC-PDM-VALAYA-EDP-75", "Parfums de Marly", "Valaya", 75),
}


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalized(value: object) -> str:
    return " ".join(
        "".join(
            c for c in unicodedata.normalize("NFKD", str(value)) if not unicodedata.combining(c)
        )
        .casefold()
        .split()
    )


def variant(row: dict) -> tuple[str, str, str, str]:
    attributes = row.get("attributes") or {}
    brand = normalized(row.get("brand", ""))
    brand = {"pdm": "parfums de marly", "bdk": "bdk parfums"}.get(brand, brand)
    name = normalized(
        row.get("name") or row.get("canonical_name") or attributes.get("canonical_name", "")
    )
    concentration = normalized(row.get("concentration") or attributes.get("concentration", ""))
    concentration = {"edp": "eau de parfum", "edt": "eau de toilette"}.get(
        concentration, concentration
    )
    volume = str(row.get("volume_ml") or attributes.get("volume_ml", ""))
    return brand, name, concentration, volume


def unique_json(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate_json_key:{key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(), object_pairs_hook=unique_json)


def prepare_review(input_bytes: bytes, registries: dict[str, dict], candidates: dict) -> dict:
    # Provenance and immutable notes/variant binding, not a generic URL trust bypass.
    if digest(input_bytes) != INPUT_SHA256:
        raise ValueError("source_packet_drift")
    packet = json.loads(input_bytes, object_pairs_hook=unique_json)
    if set(registries) != set(REGISTRIES):
        raise ValueError("missing_identity_registry")
    existing_ids, existing_variants = set(), set()
    registry_hashes = {}
    for name, registry in registries.items():
        rows = registry["products"]
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"invalid_identity_registry:{name}")
        ids = [row["product_id"] for row in rows]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate_registry_id:{name}")
        existing_ids.update(ids)
        existing_variants.update(variant(row) for row in rows)
        registry_hashes[name] = digest(canonical_bytes(registry))
    research = {}
    for row in candidates["products"]:
        key = row["candidate_id"]
        if key in research:
            raise ValueError("duplicate_candidate_id")
        research[key] = row
    records = []
    for row in packet["candidates"]:
        key = row["candidate_id"]
        expected_id, brand, name, volume = IDENTITIES[key]
        if (row["product_id"], row["brand"], row["name"], row["volume_ml"]) != (
            expected_id,
            brand,
            name,
            volume,
        ):
            raise ValueError("exact_variant_mismatch")
        prior = research.get(key)
        if not prior or variant(prior)[:3] != variant(row)[:3]:
            raise ValueError(f"candidate_identity_drift:{key}")
        if prior.get("volume_ml") is not None and str(prior["volume_ml"]) != str(volume):
            raise ValueError(f"candidate_volume_drift:{key}")
        if expected_id in existing_ids or variant(row) in existing_variants:
            raise ValueError(f"already_registered_or_staged:{key}")
        facts = {
            "candidate_id": key,
            "proposed_product_id": expected_id,
            "brand": brand,
            "name": name,
            "concentration": row["concentration"],
            "volume_ml": volume,
            "manufacturer_reference": row["manufacturer_reference"],
            "manufacturer_source": row["product_data"]["source_url"],
            "notes": row["product_data"]["notes"],
            "evidence": row["evidence"],
            "variant_evidence": row["variant_evidence"],
            "caveat": row["caveat"],
            "gtin": None,
        }
        records.append(
            {
                "review_id": f"manufacturer-review:v1:{key}",
                "state": "PRIVATE_FACTS_REVIEW_READY",
                "facts_sha256": digest(canonical_bytes(facts)),
                "facts": facts,
                "gates": {
                    "catalog_registered": False,
                    "legacy_staging_ready": False,
                    "affiliate_offer_authorized": False,
                    "image_authorized": False,
                    "public_page_authorized": False,
                    "indexing_authorized": False,
                },
            }
        )
    return {
        "contract": "dufynd.private_manufacturer_review.v1",
        "run_id": "DUFYND-20261013-STAGING-03",
        "source_packet_sha256": INPUT_SHA256,
        "source_commit": SOURCE_COMMIT,
        "registry_sha256": registry_hashes,
        "candidate_registry_sha256": digest(canonical_bytes(candidates)),
        "scope": "private_offline_review_only",
        "registered_products": 0,
        "publication_authorized": False,
        "records": records,
    }


def write_private(output: Path, payload: dict) -> str:
    """Atomic no-clobber receipt; reruns of identical input are byte-identical."""
    if output.is_symlink() or output.resolve().is_relative_to(ROOT):
        raise ValueError("output_must_be_private_and_outside_checkout")
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = canonical_bytes(payload)
    fd, temporary = tempfile.mkstemp(prefix=".manufacturer-review-", dir=output.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, output, follow_symlinks=False)
        except FileExistsError:
            # Do not follow symlinks even if a concurrent process created the target.
            existing = os.open(output, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(existing, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
                    raise ValueError("existing_receipt_not_private_regular_file") from None
                if stream.read() != data:
                    raise ValueError("conflicting_review_checkpoint") from None
            return "UNCHANGED"
        directory = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return "CREATED"
    finally:
        os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional private JSON outside the checkout; never a website route",
    )
    args = parser.parse_args()
    data = ROOT / "examples/retail/data"
    try:
        payload = prepare_review(
            INPUT.read_bytes(),
            {name: read_json(data / name) for name in REGISTRIES},
            read_json(data / "scentai_catalog_candidates.json"),
        )
        status = write_private(args.output, payload) if args.output else "VALIDATED_NO_WRITE"
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, f"HOLD: {error}\n")
    print(
        json.dumps(
            {
                "status": status,
                "private_review_records": len(payload["records"]),
                "registered_products": 0,
                "receipt_sha256": digest(canonical_bytes(payload)),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
