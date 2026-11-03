"""Check *official* CJ product-feed availability for one scoped Notino advertiser.

Read only: does not query product prices, generate CJ links, write offers or
treat publisher program membership as proof that a product feed exists.
Credentials and both CJ company IDs must be provided through environment
variables; never derive an advertiser company ID from a click-tracking URL.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

CJ_GRAPHQL = "https://ads.api.cj.com/query"
MAX_RESPONSE_BYTES = 128 * 1024


def _company_id(value: str) -> str:
    if not re.fullmatch(r"[0-9]{1,20}", value) or int(value) == 0:
        raise ValueError("cj_company_id_must_be_explicit_numeric")
    return value


def build_feed_query(company_id: str, notino_advertiser_id: str) -> str:
    """Use the documented publisher productFeeds query, scoped to one advertiser."""
    publisher = _company_id(company_id)
    advertiser = _company_id(notino_advertiser_id)
    return (
        "{ productFeeds("
        f'companyId: "{publisher}", partnerIds: ["{advertiser}"]'
        ") { totalCount count resultList { adId feedName advertiserId "
        "advertiserName productCount lastUpdated currency language sourceFeedType } } }"
    )


def parse_feed_response(
    payload: Any,
    *,
    notino_advertiser_id: str,
    checked_at: datetime,
) -> dict[str, Any]:
    """A visible feed is only a candidate, never current SKU/stock evidence."""
    advertiser = _company_id(notino_advertiser_id)
    if checked_at.tzinfo is None:
        return {"status": "CJ_REFERENCE_CLOCK_INVALID", "feeds": []}
    if not isinstance(payload, dict) or payload.get("errors"):
        return {"status": "CJ_GRAPHQL_RESPONSE_REJECTED", "feeds": []}
    data = payload.get("data")
    collection = data.get("productFeeds") if isinstance(data, dict) else None
    if not isinstance(collection, dict):
        return {"status": "CJ_PRODUCT_FEEDS_UNAVAILABLE", "feeds": []}
    rows = collection.get("resultList")
    if not isinstance(rows, list) or len(rows) > 100:
        return {"status": "CJ_FEED_COLLECTION_INVALID", "feeds": []}
    total, count = collection.get("totalCount"), collection.get("count")
    if (
        type(total) is not int
        or type(count) is not int
        or count < 0
        or total < count
        or count != len(rows)
    ):
        return {"status": "CJ_FEED_COUNTS_UNTRUSTWORTHY", "feeds": []}
    if total != count:
        return {"status": "CJ_FEED_INVENTORY_INCOMPLETE", "feeds": []}
    if any(not isinstance(row, dict) or str(row.get("advertiserId")) != advertiser for row in rows):
        return {"status": "CJ_ADVERTISER_SCOPE_MISMATCH", "feeds": []}

    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for row in rows:
        ad_id = str(row.get("adId") or "")
        if not re.fullmatch(r"[0-9]{1,20}", ad_id) or ad_id in seen:
            return {"status": "CJ_FEED_ID_MISSING_OR_DUPLICATE", "feeds": []}
        seen.add(ad_id)
        quantity = row.get("productCount")
        if type(quantity) is not int or quantity < 0:
            return {"status": "CJ_FEED_PRODUCT_COUNT_INVALID", "feeds": []}
        stamp = row.get("lastUpdated")
        try:
            updated = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            if updated.tzinfo is None:
                raise ValueError("missing timezone")
        except (TypeError, ValueError):
            return {"status": "CJ_FEED_LAST_UPDATED_INVALID", "feeds": []}
        age_seconds = (checked_at.astimezone(UTC) - updated.astimezone(UTC)).total_seconds()
        if age_seconds < -300:
            return {"status": "CJ_FEED_LAST_UPDATED_IN_FUTURE", "feeds": []}
        candidates.append(
            {
                "feed_id": ad_id,
                "advertiser_id": advertiser,
                "publisher_partnership_verified": False,
                "feed_name": str(row.get("feedName") or "")[:160],
                "product_count": quantity,
                "feed_last_updated_at": updated.astimezone(UTC).isoformat(),
                "feed_metadata_within_72h": 0 <= age_seconds <= 72 * 3600,
                "currency": str(row.get("currency") or "")[:8],
                "source_feed_type": str(row.get("sourceFeedType") or "")[:48],
            }
        )
    return {
        "status": (
            "CJ_FEED_CANDIDATES_VISIBLE_NEED_SKU_EVIDENCE"
            if candidates
            else "CJ_NO_FEED_FOR_SCOPED_ADVERTISER"
        ),
        "feeds": candidates,
    }


def check_notino_feeds(
    *,
    token: str,
    company_id: str,
    notino_advertiser_id: str,
    now: datetime | None = None,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """At most one authorized, timeout-bounded request; never retry an auth error."""
    result: dict[str, Any] = {
        "schema_version": 1,
        "source": "official_cj_product_feed_api",
        "merchant": "notino",
        "status": "CJ_CREDENTIALS_OR_COMPANY_IDS_NOT_CONFIGURED",
        "feeds": [],
        "current_sku_prices_verified": 0,
        "stock_and_shipping_verified": False,
        "affiliate_links_generated": 0,
        "offer_activation_authorized": False,
        "image_rights_authorized": False,
        "network_requests": 0,
        "database_writes": 0,
    }
    if not token or not company_id or not notino_advertiser_id:
        return result
    try:
        query = build_feed_query(company_id, notino_advertiser_id)
    except ValueError:
        return result | {"status": "CJ_COMPANY_ID_CONFIG_INVALID"}
    stamp = now or datetime.now(UTC)
    if stamp.tzinfo is None:
        return result | {"status": "CJ_REFERENCE_CLOCK_INVALID"}
    try:
        with httpx.Client(timeout=8, follow_redirects=False, transport=transport) as client:
            response = client.post(
                CJ_GRAPHQL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={"query": query},
            )
        if response.status_code in {401, 403}:
            return result | {
                "status": "CJ_AUTHORIZATION_NOT_CONFIRMED",
                "network_requests": 1,
            }
        if response.status_code == 429:
            return result | {
                "status": "CJ_RATE_LIMITED_NO_RETRY",
                "network_requests": 1,
            }
        response.raise_for_status()
        if len(response.content) > MAX_RESPONSE_BYTES:
            return result | {
                "status": "CJ_RESPONSE_TOO_LARGE",
                "network_requests": 1,
            }
        observed = parse_feed_response(
            response.json(),
            notino_advertiser_id=notino_advertiser_id,
            checked_at=stamp,
        )
        return (
            result
            | observed
            | {
                "network_requests": 1,
                "feed_inventory_checked_at": stamp.astimezone(UTC).isoformat(),
            }
        )
    except (httpx.HTTPError, ValueError, TypeError):
        return result | {
            "status": "CJ_TRANSPORT_OR_RESPONSE_FAILED",
            "network_requests": 1,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = check_notino_feeds(
        token=os.getenv("CJ_PRODUCT_FEED_TOKEN", ""),
        company_id=os.getenv("CJ_PUBLISHER_COMPANY_ID", ""),
        notino_advertiser_id=os.getenv("CJ_NOTINO_ADVERTISER_COMPANY_ID", ""),
    )
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0 if report["status"] == "CJ_FEED_CANDIDATES_VISIBLE_NEED_SKU_EVIDENCE" else 20


if __name__ == "__main__":
    raise SystemExit(main())
