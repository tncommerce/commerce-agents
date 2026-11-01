"""Prepare two source-bound batches of editorial fragrance profiles; never publish.

The generated JSON packets are *review-only* and deliberately not read by the
public website. No product photos, affiliate URLs, prices or availability
observations may enter this pathway.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from scripts.report_dufynd_discovery_release import evaluate, evidence_digest
from scripts.dufynd_localize_note_descriptions import labels, localized_description

DATA = Path("examples/retail/data")
WAVE_1_IDS = (
    "SC-CAROLINA-HERRERA-GOOD-GIRL-EDP-80",
    "SC-CHANEL-COCO-MADEMOISELLE-EDP-100",
    "SC-PRADA-PARADOXE-EDP-90",
    "SC-BURBERRY-GODDESS-EDP-100",
    "SC-GUCCI-FLORA-GORGEOUS-GARDENIA-EDP-100",
    "SC-VALENTINO-DONNA-BORN-IN-ROMA-EDP-100",
    "SC-CHLOE-CHLOE-EDP-100",
    "SC-CHLOE-NOMADE-EDP-75",
    "SC-ARMANI-SI-EDP-100",
    "SC-GUERLAIN-MON-GUERLAIN-EDP-100",
    "SC-MUGLER-ALIEN-EDP-90",
    "SC-DIOR-JADORE-EDP-100",
    "SC-DIOR-HYPNOTIC-POISON-EDT-100",
    "SC-NARCISO-RODRIGUEZ-PURE-MUSC-EDP-100",
    "SC-CALVIN-KLEIN-EUPHORIA-EDP-100",
    "SC-LATTAFA-ECLAIRE-EDP-100",
    "SC-AFNAN-9-PM-POUR-FEMME-EDP-100",
    "SC-YSL-Y-EDP-100",
    "SC-JPG-LE-MALE-LE-PARFUM-125",
    "SC-VIKTOR-ROLF-SPICEBOMB-EXTREME-EDP-90",
)
WAVE_NAMES = ("dufynd_facts_wave_01_review.json", "dufynd_facts_wave_02_review.json")
NOTE_KEYS = ("top", "heart", "base", "key")


def _load(directory: Path, name: str) -> dict:
    return json.loads((directory / name).read_text(encoding="utf-8"))


def _source_url(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("source_url_missing")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or any(ord(char) < 32 for char in value)
    ):
        raise ValueError("source_url_invalid")
    return value


def editorial_description(fact: dict) -> tuple[str, str]:
    """Extend existing source text using documented notes only, never infer a pyramid."""
    summary = str(fact.get("summary_de") or "").strip()
    if len(summary) < 35:
        raise ValueError("description_missing")
    notes = fact.get("notes") or {}
    groups = {key: notes.get(key) or [] for key in NOTE_KEYS}
    if not all(
        isinstance(values, list) and all(isinstance(v, str) and v.strip() for v in values)
        for values in groups.values()
    ):
        raise ValueError("notes_invalid")
    if all(groups[key] for key in ("top", "heart", "base")):
        kind = "documented_pyramid"
    else:
        observed = [value for key in NOTE_KEYS for value in groups[key]]
        if not observed:
            raise ValueError("notes_missing")
        kind = "documented_notes_only"
    return localized_description(fact, labels()), kind


def review_record(fact: dict, pilot: dict) -> dict:
    """Validate exact identity/source digest and preserve every public release gate."""
    evaluation = evaluate(fact, pilot)
    if (
        evaluation["ready_for_owner_review"] is not True
        or evaluation["public_release_eligible"] is not False
        or evaluation["blockers"] != ["owner_release_approval"]
        or pilot.get("owner_release_approved") is not False
        or fact.get("publication_authorized") is not False
    ):
        raise ValueError("source_or_owner_gate_not_ready")
    identity = fact.get("identity") or {}
    notes_source = fact.get("notes_source") or {}
    if not identity.get("verified") or not str(identity.get("value") or "").strip():
        raise ValueError("identity_not_verified")
    identity_url = _source_url(identity.get("source_url"))
    notes_url = _source_url(notes_source.get("url"))
    seo = pilot.get("seo") or {}
    if seo.get("public_path") != f"/duft/{pilot['slug']}":
        raise ValueError("public_path_variant_mismatch")
    if not str(seo.get("title") or "").strip() or not str(seo.get("description") or "").strip():
        raise ValueError("seo_source_missing")
    desc, kind = editorial_description(fact)
    return {
        "product_id": fact["product_id"],
        "slug": pilot["slug"],
        "brand": fact["brand"],
        "name": fact["name"],
        "concentration": fact["concentration"],
        "volume_ml": fact["volume_ml"],
        "summary_de": fact["summary_de"],
        "editorial_description_de": desc,
        "notes": {key: list(fact.get("notes", {}).get(key) or []) for key in NOTE_KEYS},
        "notes_display_kind": kind,
        "identity": {
            "kind": identity["kind"],
            "value": identity["value"],
            "source_url": identity_url,
        },
        "notes_source_url": notes_url,
        "facts_checked_at": fact["checked_at"],
        "evidence_sha256": evidence_digest(fact),
        "seo": {
            "title": seo["title"],
            "description": seo["description"],
            "public_path": seo["public_path"],
        },
        "visual_mode": "neutral_studio_card_no_packshot",
        "commerce_mode": "no_merchant_offer_no_price",
        "publication_authorized": False,
        "indexing_approved": False,
    }


def build_review_waves(directory: Path = DATA) -> list[dict]:
    """Build one 20-profile and one 21-profile packet from existing vetted facts."""
    fact_rows = _load(directory, "dufynd_discovery_qualification.json")["products"]
    pilot_rows = _load(directory, "dufynd_release_pilots.json")["pilots"]
    catalog_rows = _load(directory, "catalog.json")["products"]
    facts = {row["product_id"]: row for row in fact_rows}
    pilots = {row["product_id"]: row for row in pilot_rows}
    if len(facts) != len(fact_rows) or len(pilots) != len(pilot_rows):
        raise ValueError("duplicate_product_id")
    if len({row["slug"] for row in pilot_rows}) != len(pilot_rows):
        raise ValueError("duplicate_slug")
    if len(facts) != 41 or set(facts) != set(pilots):
        raise ValueError("source_inventory_changed_requires_review")
    if len(WAVE_1_IDS) != 20 or len(set(WAVE_1_IDS)) != 20:
        raise ValueError("wave_one_not_exactly_twenty")
    if not set(WAVE_1_IDS).issubset(facts):
        raise ValueError("unknown_wave_one_product")
    canonical_ids = {
        row["product_id"]
        for row in catalog_rows
        if str(row.get("product_id") or "").startswith("SC-") and row.get("category") == "fragrance"
    }
    if canonical_ids & set(facts):
        raise ValueError("candidate_already_in_canonical_catalog")
    remaining = [row["product_id"] for row in pilot_rows if row["product_id"] not in WAVE_1_IDS]
    if len(remaining) != 21:
        raise ValueError("wave_two_not_exactly_twenty_one")
    waves = []
    for number, ids in enumerate((WAVE_1_IDS, remaining), start=1):
        profiles = [review_record(facts[product_id], pilots[product_id]) for product_id in ids]
        waves.append(
            {
                "schema_version": 1,
                "batch_id": f"DUFYND-FACTS-ONLY-WAVE-{number:02d}",
                "status": "REVIEW_ONLY_NOT_PUBLISHED",
                "source": "existing_qualified_facts_and_curated_review_pilots",
                "new_public_profiles": 0,
                "public_release_authorized": False,
                "merchant_offer_activation": False,
                "new_images_published": False,
                "prices_or_tracking_links_added": False,
                "profile_count": len(profiles),
                "profiles": profiles,
            }
        )
    return waves


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-committed", action="store_true")
    args = parser.parse_args()
    waves = build_review_waves()
    if args.verify_committed:
        for filename, expected in zip(WAVE_NAMES, waves, strict=True):
            if _load(DATA, filename) != expected:
                raise ValueError(f"review_packet_mismatch:{filename}")
    print(
        json.dumps(
            {
                "status": "REVIEW_READY_OWNER_RELEASE_HELD",
                "counts": [wave["profile_count"] for wave in waves],
                "public_profile_count_changed": 0,
                "merchant_offer_count_changed": 0,
                "source_or_rights_claims_added": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
