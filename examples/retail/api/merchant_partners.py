from __future__ import annotations

import json
from datetime import UTC, datetime
from ipaddress import ip_address
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlparse

from pydantic import BaseModel, Field

MAX_FUTURE_CLOCK_SKEW_HOURS = 5 / 60

PartnerStatus = Literal[
    "active",
    "pending_affiliate_link",
    "paused",
    "rejected",
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


def _public_hostname(value: str | None) -> bool:
    hostname = str(value or "").strip().casefold().rstrip(".")
    if not hostname or hostname == "localhost" or hostname.endswith(".localhost"):
        return False

    try:
        return ip_address(hostname).is_global
    except ValueError:
        return True


def _valid_https_url(value: str | None) -> bool:
    if not value:
        return False

    parsed = urlparse(value)
    return bool(
        parsed.scheme == "https"
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
        and _public_hostname(parsed.hostname)
    )


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

            if age_hours < -MAX_FUTURE_CLOCK_SKEW_HOURS or age_hours > self.max_age_hours:
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


def _normalized_hostname(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().casefold()
    if normalized.startswith("www."):
        normalized = normalized[4:]
    return normalized or None


def partner_product_deeplink_url(
    partner: MerchantPartner,
    *,
    destination_url: str,
    clickref: str | None = None,
) -> str | None:
    """Build a guarded Awin product deeplink from an already verified partner link.

    The destination must stay on the same advertiser host that is encoded in the
    verified partner homepage link. This helper only builds a candidate URL; it
    does not activate an offer or change routing.
    """

    affiliate_url = partner.affiliate_url
    if not affiliate_url:
        return None

    parsed_affiliate = urlparse(affiliate_url)
    if parsed_affiliate.scheme != "https" or parsed_affiliate.hostname not in {
        "awin1.com",
        "www.awin1.com",
    }:
        return None

    query = parse_qsl(parsed_affiliate.query, keep_blank_values=True)
    verified_destination = next(
        (value for key, value in query if key.casefold() == "ued"),
        None,
    )
    if not verified_destination:
        return None

    parsed_verified = urlparse(verified_destination)
    parsed_destination = urlparse(destination_url.strip())
    if (
        parsed_verified.scheme != "https"
        or not parsed_verified.hostname
        or not _public_hostname(parsed_verified.hostname)
        or parsed_destination.scheme != "https"
        or not parsed_destination.hostname
        or not _public_hostname(parsed_destination.hostname)
        or parsed_destination.username is not None
        or parsed_destination.password is not None
    ):
        return None

    if _normalized_hostname(parsed_verified.hostname) != _normalized_hostname(
        parsed_destination.hostname
    ):
        return None

    deeplink_query = [
        (key, value) for key, value in query if key.casefold() not in {"ued", "clickref"}
    ]
    deeplink_query.append(("ued", destination_url.strip()))
    if clickref:
        deeplink_query.append(("clickref", clickref))

    return parsed_affiliate._replace(query=urlencode(deeplink_query)).geturl()


def customer_partner_payload(
    partner: MerchantPartner,
) -> dict:
    return {
        "merchant_id": partner.merchant_id,
        "merchant_name": partner.merchant_name,
        "description": partner.description,
    }
