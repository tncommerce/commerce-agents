"""Evaluate discovery publication separately from affiliate availability; never publish."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

DATA = Path("examples/retail/data")


def evidence_digest(fact: dict) -> str:
    return hashlib.sha256(json.dumps(fact, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def evaluate(fact: dict, pilot: dict) -> dict:
    blockers = []
    identity = fact.get("identity", {})
    if not identity.get("verified") or identity.get("kind") not in {
        "gtin",
        "manufacturer_reference",
    }:
        blockers.append("identity_evidence")
    if not fact.get("facts_only") or fact.get("community_data_included") is not False:
        blockers.append("facts_scope")
    if not any(fact.get("notes", {}).values()) or not fact.get("notes_source", {}).get("url"):
        blockers.append("notes_source")
    expected = pilot.get("expected_variant", {})
    if any(
        expected.get(k) != fact.get(k)
        for k in ("product_id", "brand", "name", "concentration", "volume_ml")
    ):
        blockers.append("variant_mismatch")
    if pilot.get("evidence_sha256") != evidence_digest(fact):
        blockers.append("evidence_changed_requires_review")
    visual = pilot.get("visual", {})
    if not (
        visual.get("kind") == "dufynd_original_vector_illustration"
        and visual.get("contains_product_replica") is False
        and visual.get("third_party_asset_used") is False
        and visual.get("label")
    ):
        blockers.append("visual_rights_or_label")
    ready_for_review = not blockers
    if pilot.get("owner_release_approved") is not True:
        blockers.append("owner_release_approval")
    else:
        # A historical boolean is not a source/design/QA-bound authorization.
        blockers.append("use_bound_release_authorization_pipeline")
    return {
        "product_id": fact["product_id"],
        "variant": expected,
        "identity_kind": identity.get("kind"),
        "ready_for_owner_review": ready_for_review,
        "public_release_eligible": not blockers,
        "blockers": blockers,
        "original_photo_status": pilot.get("original_photo_status"),
        "affiliate_offer_included": False,
        "evidence_sha256": evidence_digest(fact),
    }


def report() -> dict:
    facts = {
        r["product_id"]: r
        for r in json.loads((DATA / "dufynd_discovery_qualification.json").read_text())["products"]
    }
    pilots = json.loads((DATA / "dufynd_release_pilots.json").read_text())["pilots"]
    for key in ("product_id", "slug"):
        if len({p[key] for p in pilots}) != len(pilots):
            raise ValueError(f"Duplicate review {key}")
    return {
        "mode": "read_only_no_publication",
        "profiles": [evaluate(facts[p["product_id"]], p) for p in pilots],
    }


if __name__ == "__main__":
    print(json.dumps(report(), ensure_ascii=False, indent=2))
