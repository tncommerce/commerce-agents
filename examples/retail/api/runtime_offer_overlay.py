"""Opt-in, fail-closed, exact-identity live offer snapshots; no merchant fetching."""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx

SUPABASE_PROJECT = "https://bqsdxaagklpkxioaqdqa.supabase.co"
IDENTITY_FIELDS = (
    "offer_id", "product_id", "merchant_id", "merchant_product_id",
    "variant_label", "product_url", "affiliate_url", "network",
)
_cache: dict[str, tuple[float, dict[str, Any] | None]] = {}


def contract_fingerprint(row: dict[str, Any]) -> str:
    identity = {field: row.get(field) for field in IDENTITY_FIELDS}
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def accept_snapshot(
    row: dict[str, Any], snapshot: dict[str, Any] | None, *, now: datetime | None = None
) -> dict[str, Any] | None:
    """Only price, shipping, stock and verified_at may change, never the link."""
    if not isinstance(snapshot, dict):
        return None
    if snapshot.get("offer_id") != row.get("offer_id"):
        return None
    if snapshot.get("identity_sha256") != contract_fingerprint(row):
        return None
    if snapshot.get("verification_method") != "certified_merchant_observation":
        return None
    if snapshot.get("source_url") != row.get("product_url"):
        return None
    if snapshot.get("currency") != "EUR" or row.get("currency") != "EUR":
        return None
    if not isinstance(snapshot.get("evidence_reference"), str):
        return None
    if not 12 <= len(snapshot["evidence_reference"]) <= 500:
        return None
    try:
        verified = datetime.fromisoformat(str(snapshot["verified_at"]).replace("Z", "+00:00"))
        if verified.tzinfo is None:
            return None
        age = ((now or datetime.now(UTC)).astimezone(UTC) - verified.astimezone(UTC)).total_seconds()
        if not -300 <= age <= 72 * 3600:
            return None
        price, shipping, stock = snapshot["price"], snapshot["shipping_cost"], snapshot["in_stock"]
        if isinstance(price, bool) or not isinstance(price, (int, float)) or not 0 < price < 100000:
            return None
        if shipping is not None and (
            isinstance(shipping, bool) or not isinstance(shipping, (int, float))
            or not 0 <= shipping < 10000
        ):
            return None
        if not isinstance(stock, bool):
            return None
        label = snapshot.get("shipping_label")
        if label is not None and (not isinstance(label, str) or len(label) > 160):
            return None
        return row | {
            "price": price,
            "shipping_cost": shipping,
            "shipping_label": label,
            "in_stock": stock,
            "currency": "EUR",
            "last_updated_at": verified.astimezone(UTC).isoformat(),
        }
    except (ValueError, TypeError, KeyError, OverflowError):
        return None


def runtime_snapshot(offer_id: str) -> dict[str, Any] | None:
    """Read private DB evidence only; never click a merchant or manufacture a date."""
    if os.getenv("DUFYND_RUNTIME_OFFERS_ENABLED") != "1":
        return None
    merchant = offer_id.split("-", 1)[0]
    allowed = {
        m.strip() for m in os.getenv("DUFYND_RUNTIME_OFFERS_MERCHANTS", "notino").split(",")
        if m.strip()
    }
    if merchant not in allowed:
        return None
    if os.getenv("SUPABASE_URL", "").rstrip("/") != SUPABASE_PROJECT:
        return None
    key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key or len(key) < 24:
        return None
    cached = _cache.get(offer_id)
    if cached and time.monotonic() - cached[0] < 45:
        return cached[1]
    headers = {"apikey": key, "Accept": "application/json"}
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    query = urlencode({"offer_id": "eq." + offer_id, "select": "*", "limit": "1"})
    result = None
    try:
        with httpx.Client(timeout=1.5, follow_redirects=False) as client:
            response = client.get(
                f"{SUPABASE_PROJECT}/rest/v1/dufynd_live_offer_snapshots?{query}",
                headers=headers,
            )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
            result = data[0]
    except (httpx.HTTPError, ValueError, TypeError):
        pass
    _cache[offer_id] = (time.monotonic(), result)
    return result
