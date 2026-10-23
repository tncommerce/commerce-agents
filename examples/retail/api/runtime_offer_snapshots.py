"""Server-only, opt-in DUFYND offer snapshots; never a source of URLs.

Price, stock and shipping may refresh independently of a Git/Render deployment.
The canonical product, merchant, exact variant and affiliate destination always
come from the already released merchant_offers.json. No unverified snapshot can
make an offer eligible. Production behavior remains unchanged until explicitly
enabled after migration, source onboarding and owner release approval.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

PROJECT_URL = "https://bqsdxaagklpkxioaqdqa.supabase.co"
TABLE = "dufynd_runtime_offer_snapshots_v1"
CACHE_SECONDS = 30
MAX_AGE_SECONDS = 72 * 3600
MAX_FUTURE_SKEW_SECONDS = 300
SOURCE_TYPES = {"official_network_feed", "authorized_merchant_api", "direct_merchant_review"}
IDENTITY_FIELDS = (
    "offer_id",
    "product_id",
    "merchant_id",
    "merchant_product_id",
    "variant_label",
    "product_url",
    "affiliate_url",
    "network",
    "currency",
)

_cache: dict[tuple[str, ...], tuple[float, dict[str, dict[str, Any]] | None]] = {}
_lock = threading.Lock()


def runtime_offer_snapshots_enabled() -> bool:
    """Explicit fail-closed release switch, disabled by default."""
    return os.getenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "") == "enabled"


def identity_hash(canonical: dict[str, Any]) -> str:
    """Hash only fields that data refreshes are forbidden to change."""
    frozen = {field: canonical.get(field) for field in IDENTITY_FIELDS}
    encoded = json.dumps(frozen, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _safe_amount(value: Any, *, allow_zero: bool = False) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError("invalid_money_type")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid_money_value") from exc
    if (
        not amount.is_finite()
        or amount > Decimal("100000")
        or amount < 0
        or (not allow_zero and amount == 0)
        or amount.as_tuple().exponent < -2
    ):
        raise ValueError("invalid_money_amount")
    return float(amount)


def _verified_at(value: Any, *, now: datetime) -> datetime:
    if not isinstance(value, str):
        raise ValueError("missing_verified_at")
    try:
        checked = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("bad_verified_at") from exc
    if checked.tzinfo is None:
        raise ValueError("verified_at_without_timezone")
    age = (now.astimezone(UTC) - checked.astimezone(UTC)).total_seconds()
    if not -MAX_FUTURE_SKEW_SECONDS <= age <= MAX_AGE_SECONDS:
        raise ValueError("expired_or_future_source")
    return checked.astimezone(UTC)


def apply_runtime_snapshot(
    canonical: dict[str, Any],
    snapshot: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """A validated snapshot can alter commerce values, NEVER a route or SKU."""
    if not isinstance(snapshot, dict):
        return None
    for field in ("offer_id", "product_id", "merchant_id", "merchant_product_id"):
        if snapshot.get(field) != canonical.get(field):
            return None
    if snapshot.get("identity_sha256") != identity_hash(canonical):
        return None
    if snapshot.get("decision") != "verified":
        return None
    if snapshot.get("source_type") not in SOURCE_TYPES:
        return None
    if not isinstance(snapshot.get("source_ref"), str) or not (
        3 <= len(snapshot["source_ref"]) <= 260
    ):
        return None
    if not re.fullmatch(r"[0-9a-f]{64}", str(snapshot.get("evidence_sha256", ""))):
        return None
    if not isinstance(snapshot.get("in_stock"), bool):
        return None
    if snapshot.get("currency") != "EUR" or canonical.get("currency") != "EUR":
        return None
    try:
        checked = _verified_at(snapshot.get("verified_at"), now=now or datetime.now(UTC))
        price = _safe_amount(snapshot.get("price"))
        shipping = _safe_amount(snapshot.get("shipping_cost"), allow_zero=True)
    except (TypeError, ValueError, OverflowError):
        return None
    if price is None:
        return None

    label = (
        "Versand beim Händler prüfen"
        if shipping is None
        else ("Gratis Versand" if shipping == 0 else f"{shipping:.2f} € Versand")
    )
    # No URLs, network links, SKU names, merchant IDs, claims or price labels
    # from untrusted runtime data are allowed to replace the released contract.
    return canonical | {
        "price": price,
        "shipping_cost": shipping,
        "shipping_label": label,
        "in_stock": snapshot["in_stock"],
        "last_updated_at": checked.isoformat(),
        "data_source": "certified_runtime_offer_snapshot",
    }


def load_runtime_snapshots(
    canonical_rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]] | None:
    """Read just the selected offers in one bounded private request.

    None means the backend or auth is unavailable; callers must fail closed.
    {} is a successful but empty result: nothing is eligible. Both endpoints
    (offer list AND clickout) use this same decision, never separate trust.
    """
    if not canonical_rows:
        return {}
    ids = tuple(sorted({str(row["offer_id"]) for row in canonical_rows}))
    if len(ids) > 100 or any(not re.fullmatch(r"[A-Za-z0-9._:-]{1,120}", s) for s in ids):
        return None
    cached = _cache.get(ids)
    if cached is not None and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]

    key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if url != PROJECT_URL or not key:
        return None

    headers = {"apikey": key}
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    fields = (
        "offer_id,product_id,merchant_id,merchant_product_id,identity_sha256,"
        "price,shipping_cost,in_stock,currency,verified_at,decision,"
        "source_type,source_ref,evidence_sha256"
    )
    result: dict[str, dict[str, Any]] | None = None
    try:
        with httpx.Client(timeout=2, follow_redirects=False) as client:
            response = client.get(
                f"{PROJECT_URL}/rest/v1/{TABLE}",
                headers=headers,
                params={
                    "offer_id": f"in.({','.join(ids)})",
                    "select": fields,
                    "limit": str(len(ids) + 1),
                },
            )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and len(data) <= len(ids):
            rows = [r for r in data if isinstance(r, dict)]
            selected = {r.get("offer_id"): r for r in rows}
            if len(selected) == len(rows) and all(k in ids for k in selected):
                result = selected
    except (httpx.HTTPError, ValueError, TypeError):
        pass

    with _lock:
        if len(_cache) >= 200:
            _cache.clear()
        _cache[ids] = (time.monotonic(), result)
    return result
