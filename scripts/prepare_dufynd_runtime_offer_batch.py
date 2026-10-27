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
from decimal import Decimal, InvalidOperation
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
# Merchant-wide HOLD is an evidence-backed revocation, NOT a fresh quote.
# The source must state why price/stock cannot be shown; we never copy an
# old total or manufacture an out-of-stock value just to suspend an offer.
HOLD_REASONS = frozenset({
    "source_unavailable", "variant_ambiguous", "shipping_unverified",
    "price_conflict", "stock_unverified", "out_of_stock",
    "merchant_withdrawn", "network_rights_unverified",
})
# The standalone rehydrator is specifically for the two immutable, already
# human-reviewed browser bundles. Further merchant batches must establish a
# new independently approved source manifest first, never trust arbitrary
# path-provided hash lists. These IDs are source Git blob checksums.
ARCHIVED_SOURCE_MANIFEST_GIT_BLOBS = {
    "dufynd-top-six-offers-20261026": "7d67409bf865bbf2689056b80bccfe3eac8e44a7",
    "dufynd-top-wave2-offers-20261026": "d76be5bfcfe3ffa2a0730b0f28cdca54c37e7803",
}


def selected_merchant_price_matches(section: str, amount: Decimal) -> bool:
    """Read the one actual selected-option euro amount, never a crossed UVP."""
    values: list[Decimal] = []
    for raw in section.splitlines():
        line = raw.strip()
        if line.startswith("UVP") or "/ Liter" in line:
            continue
        if not re.fullmatch(r"(?:\d{1,3}(?:\.\d{3})*|\d+)(?:,\d{2}|,-) €", line):
            continue
        numbers = line.split(" €", 1)[0].replace(".", "").replace(",-", ",00").replace(",", ".")
        values.append(Decimal(numbers))
    return len(values) == 1 and values[0] == amount



# This is a source-shape gate, not cryptographic proof of a retailer's
# endorsement. Reviewers must still inspect the immutable bytes/digest.
# A feed's global "Last Imported" field cannot serve as a per-SKU observation.
POSITIVE_SOURCE_PROOFS = {
    "direct_merchant_review": ("selected_variant_page", "browser_observation_sha256"),
    "official_network_feed": ("exact_sku_stock_price_shipping_row", "source_row_sha256"),
    "authorized_merchant_api": ("authorized_exact_sku_response", "api_observation_sha256"),
}


def _require_positive_source_provenance(
    supporting: dict[str, Any],
    source_type: str,
    verified_stamp: datetime,
    *,
    now: datetime,
) -> None:
    """Reject retimed old evidence before any positive DB snapshot is prepared."""
    expected = POSITIVE_SOURCE_PROOFS.get(source_type)
    if expected is None:
        raise ValueError("unsupported_positive_source_type")
    evidence_kind, digest_field = expected
    if supporting.get("source_evidence_kind") != evidence_kind:
        raise ValueError("source_per_variant_evidence_kind_required")
    digest = supporting.get(digest_field)
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("source_original_evidence_digest_required")
    source_observed_at = supporting.get("source_observed_at")
    if not isinstance(source_observed_at, str):
        raise ValueError("source_observation_time_required")
    try:
        actual = _verified_at(source_observed_at, now=now)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("source_observation_time_invalid_or_stale") from exc
    if actual != verified_stamp:
        raise ValueError("source_observation_not_equal_to_verified_at")



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

    # Duplicate source IDs could silently select the wrong merchant/SKU
    # through dict last-write-wins. Reject the entire batch instead.
    if not isinstance(canonical_rows, list) or any(
        not isinstance(row, dict) for row in canonical_rows
    ):
        raise ValueError("invalid_canonical_offer_rows")
    canonical_ids = [row.get("offer_id") for row in canonical_rows]
    if any(
        not isinstance(offer_id, str) or re.fullmatch(r"[A-Za-z0-9._:-]{1,120}", offer_id) is None
        for offer_id in canonical_ids
    ):
        raise ValueError("invalid_canonical_offer_id")
    if len(set(canonical_ids)) != len(canonical_ids):
        raise ValueError("duplicate_canonical_offer_ids")
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
        if (
            not isinstance(source_ref, str)
            or not 3 <= len(source_ref) <= 260
            or source_ref != source_ref.strip()
            or any(ord(char) < 32 or ord(char) == 127 for char in source_ref)
        ):
            raise ValueError("source_reference_required")
        stamp = _verified_at(item.get("verified_at"), now=now)
        hold_reason = None
        if decision == "verified":
            if item.get("in_stock") is not True:
                raise ValueError("verified_offer_requires_confirmed_in_stock")
            price = _safe_amount(item.get("price"))
            shipping = _safe_amount(item.get("shipping_cost"), allow_zero=True)
            if price is None:
                raise ValueError("verified_price_missing")
            if shipping is None:
                raise ValueError("verified_total_shipping_missing")
            stock = True
        else:
            # A hold must NOT echo previously approved prices or assert stock.
            # Missing merchant observations can stop buying without a quote.
            if any(item.get(key) is not None for key in
                   ("price", "shipping_cost", "in_stock")):
                raise ValueError("hold_must_omit_price_shipping_and_stock")
            hold_reason = item.get("hold_reason")
            if hold_reason not in HOLD_REASONS:
                raise ValueError("explicit_hold_reason_required")
            price = shipping = stock = None
        supporting = item.get("evidence")
        if not isinstance(supporting, dict) or not supporting:
            raise ValueError("original_source_evidence_required")
        observation = supporting.get("source_observation")
        if not isinstance(observation, str) or not observation.strip() or len(observation) > 2048:
            raise ValueError("source_observation_reference_required")
        if decision == "verified":
            _require_positive_source_provenance(supporting, kind, stamp, now=now)
        # A digest proves which original evidence packet was submitted,
        # NOT that the merchant independently endorsed its contents.
        proof_fields = {
            "batch_id": batch_id,
            "offer_id": offer_id,
            "observation": supporting,
            "verified_at": stamp.isoformat(),
        }
        if hold_reason is not None:
            proof_fields["hold_reason"] = hold_reason
        proof = json.dumps(
            proof_fields,
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
                "in_stock": stock,
                "verified_at": stamp.isoformat(),
                "decision": decision,
                "source_type": kind,
                "source_ref": source_ref,
                "evidence_sha256": hashlib.sha256(proof.encode("utf-8")).hexdigest(),
            }
        )
    return selected




def restore_direct_merchant_browser_evidence(
    canonical_rows: list[dict[str, Any]],
    original_batch: dict[str, Any],
    *,
    evidence_dir: Path,
    now: datetime,
) -> dict[str, Any]:
    """Bind one pre-existing browser observation bundle to its exact source bytes.

    This is a read-only, in-memory source attestation. Neither a file digest nor
    a browser observation proves current stock after its original 72-hour age.
    Never re-date the observation or manufacture an offer or tracking URL.
    """
    if not isinstance(original_batch, dict) or not isinstance(original_batch.get("offers"), list):
        raise ValueError("invalid_original_batch")
    items = original_batch["offers"]
    if not 1 <= len(items) <= 50 or any(not isinstance(x, dict) for x in items):
        raise ValueError("original_batch_size_or_type_invalid")
    if not isinstance(canonical_rows, list) or any(not isinstance(x, dict) for x in canonical_rows):
        raise ValueError("canonical_rows_invalid")
    ids = [x.get("offer_id") for x in canonical_rows]
    if any(not isinstance(v, str) for v in ids) or len(set(ids)) != len(ids):
        raise ValueError("canonical_offer_ids_ambiguous")
    canonical = {x["offer_id"]: x for x in canonical_rows}

    def checked_json(name: str) -> tuple[dict[str, Any], str]:
        # Fixed basename only: never read a path supplied by an untrusted row.
        path = evidence_dir / name
        payload = path.read_bytes()
        if len(payload) > 2_000_000:
            raise ValueError("source_evidence_too_large")
        checksum = hashlib.sha256(payload).hexdigest()
        if expected_hashes.get(name) != checksum:
            raise ValueError("original_source_sha256_mismatch")
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise ValueError("original_source_shape_invalid")
        return parsed, checksum

    anchor = ARCHIVED_SOURCE_MANIFEST_GIT_BLOBS.get(evidence_dir.name)
    if anchor is None:
        raise ValueError("original_source_bundle_not_approved")
    manifest_bytes = (evidence_dir / "SHA256.json").read_bytes()
    if len(manifest_bytes) > 32_000:
        raise ValueError("source_hash_manifest_too_large")
    # Git's object ID is SHA-1(b"blob <size>\\0" + bytes), not SHA-1(bytes).
    blob_prefix = b"blob " + str(len(manifest_bytes)).encode("ascii") + b"\0"
    if hashlib.sha1(blob_prefix + manifest_bytes).hexdigest() != anchor:
        raise ValueError("original_manifest_git_object_mismatch")
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict):
        raise ValueError("source_hash_manifest_invalid")
    expected_hashes = manifest
    # The incoming batch must be exactly the archived reviewed source object.
    original_input, _ = checked_json("batch-input.json")
    if original_input != original_batch:
        raise ValueError("original_batch_input_does_not_match_archived_source")
    browser, browser_hash = checked_json("merchant-browser-observations.json")
    shipping, shipping_hash = checked_json("shipping-browser-observation.json")
    observations = browser.get("rows", browser.get("observations"))
    if not isinstance(observations, list) or len(observations) != len(items):
        raise ValueError("browser_observation_count_mismatch")
    if shipping.get("url") != "https://www.topparfuemerie.de/zahlung-versand":
        raise ValueError("merchant_shipping_source_wrong")
    _verified_at(shipping.get("checked_at"), now=now)
    shipping_text = str(shipping.get("main") or "").replace("\u00a0", " ")
    fee_match = re.search(r"pauschal mit\s+(\d+,\d{2})\s*€", shipping_text)
    free_match = re.search(r"Ab einem Bestellwert von\s+(\d+,\d{2})\s*€", shipping_text)
    if not fee_match or not free_match:
        raise ValueError("merchant_shipping_rule_not_verified")
    fee = Decimal(fee_match.group(1).replace(",", "."))
    free_threshold = Decimal(free_match.group(1).replace(",", "."))
    if fee < 0 or free_threshold <= 0:
        raise ValueError("merchant_shipping_rule_invalid")

    packet = json.loads(json.dumps(original_batch, allow_nan=False))
    seen: set[str] = set()
    for item, row, updated in zip(items, observations, packet["offers"]):
        offer_id = item.get("offer_id")
        if not isinstance(offer_id, str) or offer_id in seen or offer_id not in canonical:
            raise ValueError("unreleased_or_duplicate_browser_offer")
        seen.add(offer_id)
        original = canonical[offer_id]
        if (
            item.get("decision") != "verified"
            or item.get("source_type") != "direct_merchant_review"
            or original.get("merchant_id") != "top-parfuemerie"
            or item.get("merchant_product_id") != original.get("merchant_product_id")
            or row.get("url") != original.get("product_url")
            or not isinstance(row.get("checked_at"), str)
            or not isinstance(item.get("verified_at"), str)
        ):
            raise ValueError("merchant_browser_identity_or_source_mismatch")
        stamp = _verified_at(item["verified_at"], now=now)
        actual = _verified_at(row["checked_at"], now=now)
        if stamp != actual:
            raise ValueError("original_observation_timestamp_not_equal")
        proof = item.get("evidence")
        if (
            not isinstance(proof, dict)
            or proof.get("browser_observation_sha256") != browser_hash
            or proof.get("shipping_observation_sha256") != shipping_hash
        ):
            raise ValueError("source_digest_not_bound_to_offer")
        if item.get("in_stock") is not True:
            raise ValueError("source_stock_not_confirmed")
        price = _safe_amount(item.get("price"))
        shipping_cost = _safe_amount(item.get("shipping_cost"), allow_zero=True)
        if price is None or shipping_cost is None:
            raise ValueError("source_total_price_not_confirmed")
        wanted_shipping = Decimal("0") if Decimal(str(price)) >= free_threshold else fee
        if Decimal(str(shipping_cost)) != wanted_shipping:
            raise ValueError("original_shipping_total_mismatch")

        if "main" in row:
            # The older six-source package is faithful page text rather than
            # normalized option JSON. Match the SELECTED SKU's price section,
            # not a different size, promotional UVP or per-litre price.
            main = row.get("main")
            marker = f"Artikelnummer: {item['merchant_product_id']}"
            if not isinstance(main, str) or main.count(marker) != 1:
                raise ValueError("merchant_selected_sku_not_visible")
            part = main.split(marker, 1)[1].split("In den Warenkorb", 1)[0][:320]
            ml = item.get("volume_ml")
            if type(ml) is not int or f"Menge: {ml} ml" not in part:
                raise ValueError("merchant_selected_volume_not_visible")
            amount = Decimal(str(price))
            if not selected_merchant_price_matches(part, amount):
                raise ValueError("merchant_selected_sku_price_not_visible")
            if row.get("buyVisible") is not True or row.get("buyEnabled") is not True:
                raise ValueError("merchant_buy_button_not_enabled")
            if not ("Sofort versandfertig" in part or "Lieferzeit" in part):
                raise ValueError("merchant_selected_variant_availability_missing")
        else:
            if (
                row.get("product_id") != item.get("product_id")
                or row.get("merchant_product_id") != item.get("merchant_product_id")
                or row.get("volume_ml") != item.get("volume_ml")
                or row.get("concentration") != item.get("concentration")
                or row.get("in_stock") is not True
                or row.get("purchase_button_visible") is not True
                or row.get("purchase_button_enabled") is not True
                or row.get("price") != price
                or row.get("total_price") != price + shipping_cost
                or row.get("selected_option") != f"{item['volume_ml']} ml"
            ):
                raise ValueError("merchant_structured_option_does_not_match")
        updated["evidence"]["source_observed_at"] = row["checked_at"]
        updated["evidence"]["source_evidence_kind"] = "selected_variant_page"
    return packet



def triage_batch(
    canonical_rows: list[dict[str, Any]],
    evidence: dict[str, Any],
    *,
    now: datetime,
    partners_payload: dict[str, Any] | None = None,
    mappings_payload: dict[str, Any] | None = None,
    catalog_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Read-only, exception-first review for up to 50 independent offer sources.

    This never partially applies a batch: even structurally valid rows remain
    review-only until the whole exact digest is separately owner-approved.
    Source observations, merchant URLs and monetary figures are never echoed.
    """
    if not isinstance(evidence, dict) or evidence.get("schema_version") != 1:
        raise ValueError("unsupported_batch_schema")
    batch_id = evidence.get("batch_id")
    if not isinstance(batch_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{8,120}", batch_id):
        raise ValueError("invalid_batch_id")
    items = evidence.get("offers")
    if not isinstance(items, list) or not 1 <= len(items) <= 50:
        raise ValueError("batch_size_out_of_bounds")
    if any(not isinstance(item, dict) for item in items):
        raise ValueError("invalid_offer_record")
    offer_ids = [item.get("offer_id") for item in items]
    if any(not isinstance(offer_id, str) or
           re.fullmatch(r"[A-Za-z0-9._:-]{1,120}", offer_id) is None
           for offer_id in offer_ids):
        raise ValueError("invalid_offer_id")
    if len(set(offer_ids)) != len(offer_ids):
        raise ValueError("duplicate_offer_in_batch")

    if partners_payload is None:
        partners_payload = json.loads(PARTNERS.read_text(encoding="utf-8"))
    if mappings_payload is None:
        mappings_payload = json.loads(MAPPINGS.read_text(encoding="utf-8"))
    if catalog_payload is None:
        catalog_payload = json.loads(CATALOG.read_text(encoding="utf-8"))

    results: list[dict[str, str]] = []
    for item in items:
        try:
            inspected = prepare_batch(
                canonical_rows, {**evidence, "offers": [item]},
                now=now,
                partners_payload=partners_payload,
                mappings_payload=mappings_payload,
                catalog_payload=catalog_payload,
            )[0]
        except (ValueError, TypeError, KeyError) as exc:
            # These errors are stable machine-readable gate codes. Never echo
            # arbitrary source/URL text or merchant-provided exception details.
            candidate = str(exc)
            blocker = (
                candidate
                if re.fullmatch(r"[a-z][a-z0-9_]{2,100}", candidate)
                else "unverified_or_malformed_source"
            )
            results.append({
                "offer_id": item["offer_id"],
                "status": "BLOCKED_SOURCE_EVIDENCE",
                "reason": blocker,
            })
            continue
        results.append({
            "offer_id": inspected["offer_id"],
            "status": (
                "HOLD_REVIEW_ONLY" if inspected["decision"] == "hold"
                else "COMPLETE_EVIDENCE_REVIEW_ONLY"
            ),
            "reason": "separate_batch_approval_and_release_required",
        })

    counts = {
        code: sum(row["status"] == code for row in results)
        for code in (
            "COMPLETE_EVIDENCE_REVIEW_ONLY",
            "HOLD_REVIEW_ONLY",
            "BLOCKED_SOURCE_EVIDENCE",
        )
    }
    return {
        "schema_version": 1,
        "batch_id": batch_id,
        "status": "REVIEW_ONLY_NO_IMPORT_OR_ACTIVATION",
        "offer_count": len(results),
        "counts": counts,
        "items": results,
        "database_writes": 0,
        "affiliate_clickouts": 0,
        "public_offer_activation": False,
        "all_source_evidence_approved": False,
    }


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


def verify_written_batch(prepared: list[dict[str, Any]], observed: Any) -> None:
    """A successful HTTP write is not yet a certified persisted offer batch."""
    if (
        not isinstance(observed, list)
        or len(observed) != len(prepared)
        or any(not isinstance(row, dict) for row in observed)
    ):
        raise RuntimeError("offer_batch_readback_count_or_type_mismatch")
    saved = {str(row.get("offer_id")): row for row in observed}
    expected_ids = {row["offer_id"] for row in prepared}
    if len(saved) != len(observed) or set(saved) != expected_ids:
        raise RuntimeError("offer_batch_readback_identity_mismatch")

    immutable = (
        "offer_id",
        "product_id",
        "merchant_id",
        "merchant_product_id",
        "identity_sha256",
        "currency",
        "in_stock",
        "decision",
        "source_type",
        "source_ref",
        "evidence_sha256",
    )
    for expected in prepared:
        found = saved[expected["offer_id"]]
        if any(found.get(field) != expected[field] for field in immutable):
            raise RuntimeError("offer_batch_readback_contract_mismatch")
        try:
            for field in ("price", "shipping_cost"):
                stored, submitted = found.get(field), expected[field]
                if (stored is None) != (submitted is None):
                    raise RuntimeError("offer_batch_readback_money_mismatch")
                if stored is not None and Decimal(str(stored)) != Decimal(str(submitted)):
                    raise RuntimeError("offer_batch_readback_money_mismatch")
            actual = datetime.fromisoformat(str(found["verified_at"]).replace("Z", "+00:00"))
            wanted = datetime.fromisoformat(expected["verified_at"].replace("Z", "+00:00"))
            if actual.tzinfo is None or wanted.tzinfo is None:
                raise RuntimeError("offer_batch_readback_timezone_missing")
            if actual.astimezone(UTC) != wanted.astimezone(UTC):
                raise RuntimeError("offer_batch_readback_timestamp_mismatch")
        except (ValueError, TypeError, KeyError, InvalidOperation) as exc:
            raise RuntimeError("offer_batch_readback_malformed") from exc


def apply_batch(
    prepared: list[dict[str, Any]],
    *,
    batch_id: str,
    owner_approval: str,
    transport: httpx.BaseTransport | None = None,
) -> None:
    """Atomic upsert followed by uncached, exact-row persistence verification."""
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
    with httpx.Client(timeout=8, follow_redirects=False, transport=transport) as client:
        response = client.post(
            f"{PROJECT_URL}/rest/v1/{TABLE}",
            params={"on_conflict": "offer_id"},
            headers=headers,
            json=prepared,
        )
        response.raise_for_status()
        # A successful upsert alone cannot prove exact buyer-facing persistence.
        # The REST read bypasses the 30-second public runtime snapshot cache.
        readback = client.get(
            f"{PROJECT_URL}/rest/v1/{TABLE}",
            headers={
                name: value
                for name, value in headers.items()
                if name in {"apikey", "Authorization"}
            },
            params={
                "offer_id": "in.(" + ",".join(row["offer_id"] for row in prepared) + ")",
                "select": (
                    "offer_id,product_id,merchant_id,merchant_product_id,"
                    "identity_sha256,currency,price,shipping_cost,in_stock,"
                    "verified_at,decision,source_type,source_ref,evidence_sha256"
                ),
                "limit": str(len(prepared) + 1),
            },
        )
        readback.raise_for_status()
        try:
            observed = readback.json()
        except ValueError as exc:
            raise RuntimeError("offer_batch_readback_invalid_json") from exc
        verify_written_batch(prepared, observed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--canonical", type=Path, default=CANONICAL)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--owner-approval", default="")
    parser.add_argument("--triage", action="store_true",
                        help="Print per-offer gate results without importing anything.")
    parser.add_argument("--merchant-browser-evidence-dir", type=Path,
                        help="Recheck local original SHA-256 browser and DE shipping receipts.")
    args = parser.parse_args()

    raw = json.loads(args.evidence.read_text(encoding="utf-8"))
    catalog = json.loads(args.canonical.read_text(encoding="utf-8"))["offers"]
    observed_at = datetime.now(UTC)
    if args.merchant_browser_evidence_dir is not None:
        raw = restore_direct_merchant_browser_evidence(
            catalog, raw,
            evidence_dir=args.merchant_browser_evidence_dir, now=observed_at,
        )
    if args.triage:
        if args.apply or args.owner_approval:
            parser.error("--triage cannot be combined with --apply or owner approval")
        report = triage_batch(catalog, raw, now=observed_at)
        print(json.dumps(report, ensure_ascii=False))
        return 0
    prepared = prepare_batch(catalog, raw, now=observed_at)
    if args.apply:
        try:
            apply_batch(
                prepared,
                batch_id=raw["batch_id"],
                owner_approval=args.owner_approval,
            )
        except (httpx.HTTPError, RuntimeError):
            # The POST may have committed even if the GET failed.
            parser.exit(30, "offer_batch_write_state_unconfirmed_check_audit_no_retry\n")
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
