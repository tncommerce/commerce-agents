"""Consume certified evidence without changing canonical business fields."""

from __future__ import annotations

import hashlib
import os
import threading
import time
from datetime import UTC, datetime
from typing import Any

import httpx

TARGET_OFFER = "perfumetrader-rabanne-1-million-edt-100"
PROJECT_URL = "https://bqsdxaagklpkxioaqdqa.supabase.co"
_cache: dict[str, tuple[float, dict[str, Any] | None, int]] = {}
_lock = threading.Lock()
_cache_identity: str | None = None
_identity_epoch = 0
_request_generation = 0


def _server_key() -> str | None:
    if os.getenv("SUPABASE_URL", "").rstrip("/") != PROJECT_URL:
        return None
    return os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")


def evidence_for(offer_id: str) -> dict[str, Any] | None:
    if offer_id != TARGET_OFFER:
        return None
    # Check configuration before cache access. A removed/rotated credential
    # must not inherit a prior server identity's positive or negative evidence.
    key = _server_key()
    identity = hashlib.sha256(key.encode("utf-8")).hexdigest() if key else None
    global _cache_identity, _identity_epoch, _request_generation
    with _lock:
        if identity != _cache_identity:
            _cache.clear()
            _cache_identity = identity
            _identity_epoch += 1
        if not key:
            return None
        cached = _cache.get(offer_id)
        if cached and time.monotonic() - cached[0] < 60:
            return cached[1]
        epoch = _identity_epoch
        _request_generation += 1
        generation = _request_generation

    headers = {"apikey": key}
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    value = None
    try:
        # Do not hold the lock during I/O: independent requests can finish
        # promptly, while the generation guard resolves out-of-order results.
        with httpx.Client(timeout=2, follow_redirects=False) as client:
            response = client.post(
                f"{PROJECT_URL}/rest/v1/rpc/read_dufynd_purchase_evidence",
                headers=headers,
                json={"p_offer_id": offer_id},
            )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            value = data
    except (httpx.HTTPError, ValueError):
        pass  # No date bump on outage, credentials or decoding failure.
    with _lock:
        # Also discard an in-flight result after configuration changed. The
        # epoch prevents an old read surviving A -> B -> A credential changes.
        if epoch != _identity_epoch or _server_key() != key:
            return None
        latest = _cache.get(offer_id)
        if latest is not None and latest[2] > generation:
            return latest[1]
        # A slower old positive must never overwrite a newer HOLD, missing
        # response or transport failure. No source timestamp is altered here.
        _cache[offer_id] = (time.monotonic(), value, generation)
    return value


def apply_evidence(row: dict[str, Any], evidence: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(evidence, dict) or not evidence or row.get("offer_id") != TARGET_OFFER:
        return row
    business = {k: v for k, v in row.items() if k != "last_updated_at"}
    if (
        evidence.get("source") != "certified_purchase_verification"
        or evidence.get("max_age_hours") != 72
        or evidence.get("offer_contract") != business
    ):
        return row
    # A changed stock/price/identity finding never presents the old offer as healthy.
    if evidence.get("decision") != "safe_evidence_refresh":
        return None  # Exclude through eligibility, never invent a changed stock value.
    verified_stamp = evidence.get("verified_at")
    original_stamp = row.get("last_updated_at")
    if not isinstance(verified_stamp, str) or not isinstance(original_stamp, str):
        return row
    try:
        verified = datetime.fromisoformat(verified_stamp.replace("Z", "+00:00"))
        original = datetime.fromisoformat(original_stamp.replace("Z", "+00:00"))
        age = (datetime.now(UTC) - verified).total_seconds()
        if verified.tzinfo is None or original.tzinfo is None or not -300 <= age <= 72 * 3600:
            return row
        return row | {"last_updated_at": max(original, verified).isoformat()}
    except (ValueError, TypeError, OverflowError):
        return row
