from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from .merchant_import import (
    MerchantProductMapping,
    resolve_product_id,
)


def _valid_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False

    candidate = value.strip()
    if not candidate:
        return False

    parsed = urlparse(candidate)
    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
    )


def extract_feed_image_candidates(
    rows: list[dict],
    mappings: list[MerchantProductMapping],
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []

    seen: set[tuple[str, str]] = set()

    for row_index, row in enumerate(rows):
        image_url = row.get("image_url")

        if image_url is None or not str(image_url).strip():
            continue

        if not _valid_http_url(image_url):
            invalid.append(
                {
                    "row_index": row_index,
                    "offer_id": row.get("offer_id"),
                    "merchant": row.get("merchant"),
                    "image_url": image_url,
                    "reason": "invalid_image_url",
                }
            )
            continue

        merchant = str(row.get("merchant") or "").strip()
        product_id = resolve_product_id(
            mappings,
            merchant=merchant,
            merchant_product_id=row.get(
                "merchant_product_id"
            ),
            ean=row.get("ean"),
            gtin=row.get("gtin"),
        )

        base = {
            "offer_id": row.get("offer_id"),
            "merchant": merchant,
            "merchant_id": row.get("merchant_id"),
            "merchant_name": row.get("merchant_name"),
            "merchant_product_id": row.get(
                "merchant_product_id"
            ),
            "ean": row.get("ean"),
            "gtin": row.get("gtin"),
            "image_url": str(image_url).strip(),
            "network": row.get("network"),
            "data_source": row.get("data_source"),
            "last_updated_at": row.get("last_updated_at"),
        }

        if product_id is None:
            unmatched.append(
                {
                    **base,
                    "reason": "product_mapping_not_found",
                }
            )
            continue

        dedupe_key = (
            product_id,
            str(image_url).strip(),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        candidates.append(
            {
                **base,
                "product_id": product_id,
                "review_status": "pending_review",
                "approved_image_status": (
                    "approved_feed_image"
                ),
            }
        )

    candidates.sort(
        key=lambda row: (
            str(row["product_id"]),
            str(row["merchant"]).casefold(),
            str(row["image_url"]),
        )
    )

    return {
        "candidate_count": len(candidates),
        "unmatched_count": len(unmatched),
        "invalid_count": len(invalid),
        "candidates": candidates,
        "unmatched": unmatched,
        "invalid": invalid,
    }
