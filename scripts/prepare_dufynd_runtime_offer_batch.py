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

CANONICAL = Path("examples/retail/data/merchant_offers.json")


def prepare_batch(
    canonical_rows: list[dict[str, Any]],
    evidence: dict[str, Any],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    """Validate an entire batch before producing ANY row (all-or-nothing)."""
    if evidence.get("schema_version") != 1:
        raise ValueError("unsupported_batch_schema")
    batch_id = evidence.get("batch_id")
    if not isinstance(batch_id, str) or not re.fullmatch(
        r"[A-Za-z0-9._:-]{8,120}", batch_id
    ):
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


def apply_batch(
    prepared: list[dict[str, Any]],
    *,
    batch_id: str,
    owner_approval: str,
) -> None:
    """One atomic REST upsert, recorded by database triggers per offer."""
    if owner_approval != batch_id or os.getenv("DUFYND_OFFER_BATCH_OWNER_GO") != batch_id:
        raise PermissionError("exact_batch_owner_approval_required")
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
                "count": len(prepared),
                "offers": [
                    {"offer_id": r["offer_id"], "decision": r["decision"]}
                    for r in prepared
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
