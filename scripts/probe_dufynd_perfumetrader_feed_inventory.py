"""Read the official Awin feed inventory for advertiser 11672 only.

This probe never downloads a product feed, writes an artifact, or changes
merchant/image approvals. Its stdout contains bounded, sanitized metadata only.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from urllib.parse import quote

if __package__:
    from .fetch_dufynd_awin_data_feed import (
        DEFAULT_LIST_MAX_BYTES,
        _read_url,
        parse_feed_list,
        sanitized_feed_metadata,
    )
else:
    from fetch_dufynd_awin_data_feed import (
        DEFAULT_LIST_MAX_BYTES,
        _read_url,
        parse_feed_list,
        sanitized_feed_metadata,
    )

ADVERTISER_ID = "11672"
KEY_ENV = "AWIN_DATA_FEED_API_KEY"


def probe_inventory(api_key: str) -> dict:
    api_key = api_key.strip()
    report = {
        "version": 1,
        "checked_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source": "awin_product_feed_list",
        "advertiser_id": ADVERTISER_ID,
        "status": "BLOCKED_CREDENTIAL_MISSING",
        "feeds": [],
        "feed_count": 0,
        "product_feed_downloaded": False,
        "image_publication_allowed": False,
    }
    if not api_key:
        return report

    # Reuse the reviewed bounded reader and redirect identity checks. The
    # secret-bearing URL is never returned, printed, or written to disk.
    url = "https://productdata.awin.com/datafeed/list/apikey/" + quote(api_key, safe="")
    rows = parse_feed_list(
        _read_url(
            url,
            max_bytes=DEFAULT_LIST_MAX_BYTES,
            expected_list_api_key=api_key,
        ),
        max_bytes=DEFAULT_LIST_MAX_BYTES,
    )
    inventory = [sanitized_feed_metadata(row) for row in rows]
    # A readable HTTP response is not necessarily the feed inventory. Do not
    # turn an empty/error document or missing identity columns into an absence
    # claim for this advertiser.
    if not inventory or any(
        not metadata["advertiser_id"].isdigit() or not metadata["feed_id"].isdigit()
        for metadata in inventory
    ):
        raise ValueError("awin_inventory_identity_columns_unconfirmed")
    for metadata in inventory:
        if metadata["advertiser_id"] != ADVERTISER_ID:
            continue
        # Inventory needs no download destination. Also fail closed against a
        # reflected credential/URL inside a nominally harmless CSV name field.
        metadata.pop("download_host", None)
        for key, value in metadata.items():
            if isinstance(value, str) and (
                api_key in value or quote(api_key, safe="") in value or "://" in value
            ):
                metadata[key] = "[redacted]"
        report["feeds"].append(metadata)
    report["feed_count"] = len(report["feeds"])
    if not report["feeds"]:
        report["status"] = "NO_FEEDS_LISTED_FOR_ADVERTISER"
    elif not any(feed["joined"] for feed in report["feeds"]):
        report["status"] = "FEEDS_LISTED_NO_ACTIVE_MEMBERSHIP"
    else:
        report["status"] = "FEEDS_LISTED_REVIEW_ONLY"
    return report


def main() -> int:
    try:
        report = probe_inventory(os.environ.get(KEY_ENV, ""))
    except Exception:
        # Never stringify an upstream exception: it may carry the request URL
        # (and thus the API key), response text, or a credential-bearing cause.
        report = {
            "version": 1,
            "checked_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "source": "awin_product_feed_list",
            "advertiser_id": ADVERTISER_ID,
            "status": "BLOCKED_INVENTORY_READ_OR_PARSE_FAILED",
            "product_feed_downloaded": False,
            "image_publication_allowed": False,
        }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 2 if report["status"].startswith("BLOCKED_") else 0


if __name__ == "__main__":
    raise SystemExit(main())
