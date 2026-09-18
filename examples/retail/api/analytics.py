from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


AnalyticsEventName = Literal[
    "page_view",
    "consultation_start",
    "product_open",
    "merchant_clickout",
]


class AnalyticsEventRequest(BaseModel):
    event: AnalyticsEventName
    product_id: str | None = Field(default=None, max_length=80)
    source: str | None = Field(default=None, max_length=80)


class FirstPartyAnalyticsTracker:
    """Privacy-minimized first-party product analytics for the MVP.

    We keep only a one-way session hash and coarse event context. Prompt text,
    IP addresses, user-agent strings, email addresses and customer names are
    intentionally not written to this analytics log.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    @staticmethod
    def session_key(session_id: str) -> str:
        return hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:24]

    def record(
        self,
        *,
        session_id: str,
        event: AnalyticsEventName,
        product_id: str | None = None,
        source: str | None = None,
        now: datetime | None = None,
    ) -> str:
        event_id = str(uuid4())
        occurred_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        row = {
            "event_id": event_id,
            "occurred_at": occurred_at.isoformat(),
            "session_key": self.session_key(session_id),
            "event": event,
            "product_id": product_id,
            "source": source,
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

        return event_id
