from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlparse

from pydantic import BaseModel, Field

PartnerStatus = Literal[
    "active",
    "pending_affiliate_link",
    "paused",
]


class MerchantPartner(BaseModel):
    merchant_id: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    merchant_name: str = Field(
        min_length=1,
        max_length=120,
    )
    status: PartnerStatus
    affiliate_url: str | None = None
    last_verified_at: datetime | None = None
    description: str | None = Field(
        default=None,
        max_length=180,
    )


def _valid_https_url(value: str | None) -> bool:
    if not value:
        return False

    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


class MerchantPartnerStore:
    def __init__(
        self,
        path: Path,
        *,
        max_age_hours: float = 720.0,
    ) -> None:
        self.path = path
        self.max_age_hours = max_age_hours

    def all(self) -> list[MerchantPartner]:
        if not self.path.exists():
            return []

        payload = json.loads(self.path.read_text(encoding="utf-8-sig"))
        return [MerchantPartner.model_validate(row) for row in payload.get("partners", [])]

    def active(
        self,
        *,
        now: datetime | None = None,
    ) -> list[MerchantPartner]:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        active: list[MerchantPartner] = []

        for partner in self.all():
            if partner.status != "active":
                continue
            if not _valid_https_url(partner.affiliate_url):
                continue
            if partner.last_verified_at is None:
                continue

            verified = partner.last_verified_at
            if verified.tzinfo is None:
                verified = verified.replace(tzinfo=UTC)
            age_hours = (current - verified.astimezone(UTC)).total_seconds() / 3600

            if age_hours < 0 or age_hours > self.max_age_hours:
                continue

            active.append(partner)

        return sorted(
            active,
            key=lambda partner: (
                partner.merchant_name.casefold(),
                partner.merchant_id,
            ),
        )

    def eligible(
        self,
        merchant_id: str,
        *,
        now: datetime | None = None,
    ) -> MerchantPartner | None:
        return next(
            (partner for partner in self.active(now=now) if partner.merchant_id == merchant_id),
            None,
        )


def partner_clickout_url(
    partner: MerchantPartner,
    *,
    clickref: str | None = None,
) -> str | None:
    url = partner.affiliate_url
    if not url or not clickref:
        return url

    parsed = urlparse(url)
    if parsed.hostname not in {"awin1.com", "www.awin1.com"}:
        return url

    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() != "clickref"
    ]
    query.append(("clickref", clickref))
    return parsed._replace(query=urlencode(query)).geturl()


def customer_partner_payload(
    partner: MerchantPartner,
) -> dict:
    return {
        "merchant_id": partner.merchant_id,
        "merchant_name": partner.merchant_name,
        "description": partner.description,
    }
