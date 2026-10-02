"""Consume certified evidence without changing canonical business fields."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Any

import httpx

TARGET_OFFER = "perfumetrader-rabanne-1-million-edt-100"
_cache: dict[str, tuple[float, dict[str, Any] | None]] = {}


def evidence_for(offer_id: str) -> dict[str, Any] | None:
    if offer_id != TARGET_OFFER:
        return None
    cached = _cache.get(offer_id)
    if cached and time.monotonic() - cached[0] < 60:
        return cached[1]
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if url != "https://bqsdxaagklpkxioaqdqa.supabase.co" or not key:
        return None
    headers = {"apikey": key}
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    value = None
    try:
        with httpx.Client(timeout=2, follow_redirects=False) as client:
            response = client.post(
                f"{url}/rest/v1/rpc/read_dufynd_purchase_evidence",
                headers=headers,
                json={"p_offer_id": offer_id},
            )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            value = data
    except (httpx.HTTPError, ValueError):
        pass  # No date bump on outage, credentials or decoding failure.
    _cache[offer_id] = (time.monotonic(), value)
    return value


def apply_evidence(row: dict[str, Any], evidence: dict[str, Any] | None) -> dict[str, Any] | None:
    if not evidence or row.get("offer_id") != TARGET_OFFER:
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
    try:
        verified = datetime.fromisoformat(evidence["verified_at"].replace("Z", "+00:00"))
        original = datetime.fromisoformat(row["last_updated_at"].replace("Z", "+00:00"))
        age = (datetime.now(UTC) - verified).total_seconds()
        if verified.tzinfo is None or original.tzinfo is None or not -300 <= age <= 72 * 3600:
            return row
        return row | {"last_updated_at": max(original, verified).isoformat()}
    except (ValueError, TypeError, KeyError):
        return row
