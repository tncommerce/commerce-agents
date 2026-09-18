from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field


AnalyticsEventName = Literal[
    "page_view",
    "consultation_start",
    "product_open",
    "merchant_clickout",
    "catalog_search",
    "catalog_no_results",
]


def sanitize_catalog_search_term(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = " ".join(
        value.strip().lower().split()
    )[:80]

    if len(normalized) < 2:
        return None

    if re.search(r"\S+@\S+\.\S+", normalized):
        return None

    digits_only = re.sub(r"[\s()+-]", "", normalized)
    if re.search(r"\b\d{7,}\b", digits_only):
        return None

    return normalized


class AnalyticsEventRequest(BaseModel):
    event: AnalyticsEventName
    product_id: str | None = Field(default=None, max_length=80)
    source: str | None = Field(default=None, max_length=80)
    search_term: str | None = Field(default=None, max_length=80)
    result_count: int | None = Field(default=None, ge=0)


class FirstPartyAnalyticsTracker:
    """Privacy-minimized first-party product analytics for the MVP.

    Production can persist to Supabase through its server-side REST API. Local
    development and temporary outages fall back to an append-only JSONL file.

    Prompt text, IP addresses, user-agent strings, email addresses and customer
    names are intentionally never written to the analytics store.
    """

    TABLE = "scentai_analytics_events"

    def __init__(
        self,
        path: Path,
        *,
        supabase_url: str | None = None,
        supabase_service_role_key: str | None = None,
    ) -> None:
        self.path = path
        self.supabase_url = (supabase_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.supabase_service_role_key = (
            supabase_service_role_key
            or os.getenv("SUPABASE_SECRET_KEY", "")
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        )

    @staticmethod
    def session_key(session_id: str) -> str:
        return hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:24]

    def _row(
        self,
        *,
        session_id: str,
        event: AnalyticsEventName,
        product_id: str | None,
        source: str | None,
        search_term: str | None,
        result_count: int | None,
        now: datetime | None,
    ) -> dict:
        occurred_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        return {
            "event_id": str(uuid4()),
            "occurred_at": occurred_at.isoformat(),
            "session_key": self.session_key(session_id),
            "event": event,
            "product_id": product_id,
            "source": source,
            "search_term": sanitize_catalog_search_term(search_term),
            "result_count": result_count,
        }

    def _record_local(self, row: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    async def record(
        self,
        *,
        session_id: str,
        event: AnalyticsEventName,
        product_id: str | None = None,
        source: str | None = None,
        search_term: str | None = None,
        result_count: int | None = None,
        now: datetime | None = None,
    ) -> tuple[str, str]:
        row = self._row(
            session_id=session_id,
            event=event,
            product_id=product_id,
            source=source,
            search_term=search_term,
            result_count=result_count,
            now=now,
        )

        if self.supabase_url and self.supabase_service_role_key:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(
                        f"{self.supabase_url}/rest/v1/{self.TABLE}",
                        headers={
                            "apikey": self.supabase_service_role_key,
                            **(
                                {
                                    "Authorization": f"Bearer {self.supabase_service_role_key}",
                                }
                                if self.supabase_service_role_key.startswith("eyJ")
                                else {}
                            ),
                            "Content-Type": "application/json",
                            "Prefer": "return=minimal",
                        },
                        json=row,
                    )
                    response.raise_for_status()
                return row["event_id"], "supabase"
            except httpx.HTTPError:
                # Analytics must never break the shopping experience. A local
                # fallback keeps the event available for short-term diagnosis.
                self._record_local(row)
                return row["event_id"], "local_fallback"

        self._record_local(row)
        return row["event_id"], "local"
