"""Build or apply a reviewed, exact-variant DUFYND offer batch.

No product URL or affiliate link can be authored here. Dry run is the default;
the apply path requires a matching batch-scoped owner/operations approval and
uses the already connected Supabase project/server-side key. Input observations
must come from authorized evidence, never inferred from a previous timestamp.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from examples.retail.api.runtime_offer_snapshots import (
    PROJECT_URL,
    SOURCE_TYPES,
    TABLE,
    _safe_amount,
    _verified_at,
    identity_hash,
)
from scripts.dufynd_commerce_gates import approved_affiliate_route, verify_exact_variant

CANONICAL = Path("examples/retail/data/merchant_offers.json")
PARTNERS = Path("examples/retail/data/merchant_partners.json")
MAPPINGS = Path("examples/retail/data/merchant_product_mappings.json")
CATALOG = Path("examples/retail/data/catalog.json")


def prepare_batch(
    canonical_rows: list[dict[str, Any]],
    evidence: dict[str, Any],
    *,
    now: datetime,
    partners_payload: dict[str, Any] | None = None,
    mappings_payload: dict[str, Any] | None = None,
    catalog_payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Validate one entire batch; recheck program, SKU, EAN and concentration."""
    if partners_payload is None:
        partners_payload = json.loads(PARTNERS.read_text(encoding="utf-8"))
    if mappings_payload is None:
        mappings_payload = json.loads(MAPPINGS.read_text(encoding="utf-8"))
    if catalog_payload is None:
        catalog_payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    if evidence.get("schema_version") != 1:
        raise ValueError("unsupported_batch_schema")
    batch_id = evidence.get("batch_id")
    if not isinstance(batch_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{8,120}", batch_id):
        raise ValueError("invalid_batch_id")
    items = evidence.get("offers")
    if not isinstance(items, list) or not 1 <= len(items) <= 50:
        raise ValueError("batch_size_out_of_bounds")

    allowed = {r["offer_id"]: r for r in canonical_rows}
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("invalid_offer_record")
        offer_id = item.get("offer_id")
        if not isinstance(offer_id, str) or offer_id not in allowed:
            raise ValueError("unknown_or_unreleased_offer")
        if offer_id in seen:
            raise ValueError("duplicate_offer_in_batch")
        seen.add(offer_id)
        original = allowed[offer_id]
        for field in ("product_id", "merchant_product_id", "variant_label"):
            if item.get(field) != original.get(field):
                raise ValueError("exact_product_or_variant_mismatch")
        if any(field in item for field in ("affiliate_url", "product_url", "network")):
            raise ValueError("network_or_destination_change_forbidden")

        decision = item.get("decision")
        if decision not in {"verified", "hold"}:
            raise ValueError("decision_must_be_verified_or_hold")
        if decision == "verified":
            if not approved_affiliate_route(original, partners_payload):
                raise ValueError("partner_or_approved_tracked_route_missing")
            verify_exact_variant(original, item, catalog_payload, mappings_payload)
        kind = item.get("source_type")
        if kind not in SOURCE_TYPES:
            raise ValueError("unapproved_evidence_type")
        source_ref = item.get("source_ref")
        if not isinstance(source_ref, str) or not 3 <= len(source_ref) <= 260:
            raise ValueError("source_reference_required")
        stamp = _verified_at(item.get("verified_at"), now=now)
        if not isinstance(item.get("in_stock"), bool):
            raise ValueError("stock_must_be_boolean")
        price = _safe_amount(item.get("price"))
        shipping = _safe_amount(item.get("shipping_cost"), allow_zero=True)
        if price is None:
            raise ValueError("verified_price_missing")
        supporting = item.get("evidence")
        if not isinstance(supporting, dict) or not supporting:
            raise ValueError("original_source_evidence_required")
        if not isinstance(supporting.get("source_observation"), str):
            raise ValueError("source_observation_reference_required")
        # A digest proves which original evidence packet was submitted,
        # NOT that the merchant independently endorsed its contents.
        proof = json.dumps(
            {
                "batch_id": batch_id,
                "offer_id": offer_id,
                "observation": supporting,
                "verified_at": stamp.isoformat(),
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        selected.append(
            {
                "offer_id": offer_id,
                "product_id": original["product_id"],
                "merchant_id": original["merchant_id"],
                "merchant_product_id": original.get("merchant_product_id"),
                "identity_sha256": identity_hash(original),
                "currency": "EUR",
                "price": price,
                "shipping_cost": shipping,
                "in_stock": item["in_stock"],
                "verified_at": stamp.isoformat(),
                "decision": decision,
                "source_type": kind,
                "source_ref": source_ref,
                "evidence_sha256": hashlib.sha256(proof.encode("utf-8")).hexdigest(),
            }
        )
    return selected


def batch_digest(prepared: list[dict[str, Any]], *, batch_id: str) -> str:
    """Content-address the exact evidence-backed rows, not merely a reusable ID."""
    payload = json.dumps(
        {
            "batch_id": batch_id,
            "offers": sorted(prepared, key=lambda row: row["offer_id"]),
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def apply_batch(
    prepared: list[dict[str, Any]],
    *,
    batch_id: str,
    owner_approval: str,
) -> None:
    """One atomic REST upsert, bound to a batch content hash and prior GO."""
    exact_scope = f"{batch_id}:{batch_digest(prepared, batch_id=batch_id)}"
    if owner_approval != exact_scope or os.getenv("DUFYND_OFFER_BATCH_OWNER_GO") != exact_scope:
        raise PermissionError("exact_batch_content_owner_approval_required")
    if os.getenv("SUPABASE_URL", "").rstrip("/") != PROJECT_URL:
        raise PermissionError("unexpected_supabase_project")
    key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        raise PermissionError("no_server_only_database_key")
    headers = {
        "apikey": key,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    with httpx.Client(timeout=8, follow_redirects=False) as client:
        response = client.post(
            f"{PROJECT_URL}/rest/v1/{TABLE}",
            params={"on_conflict": "offer_id"},
            headers=headers,
            json=prepared,
        )
    response.raise_for_status()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--canonical", type=Path, default=CANONICAL)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--owner-approval", default="")
    args = parser.parse_args()

    raw = json.loads(args.evidence.read_text(encoding="utf-8"))
    catalog = json.loads(args.canonical.read_text(encoding="utf-8"))["offers"]
    prepared = prepare_batch(catalog, raw, now=datetime.now(UTC))
    if args.apply:
        apply_batch(
            prepared,
            batch_id=raw["batch_id"],
            owner_approval=args.owner_approval,
        )
    print(
        json.dumps(
            {
                "status": "APPLIED" if args.apply else "DRY_RUN_ONLY",
                "batch_id": raw["batch_id"],
                "batch_sha256": batch_digest(prepared, batch_id=raw["batch_id"]),
                "count": len(prepared),
                "offers": [
                    {"offer_id": r["offer_id"], "decision": r["decision"]} for r in prepared
                ],
                "publication_change": False,
                "affiliate_link_change": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
