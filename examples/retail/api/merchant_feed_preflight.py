from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

REQUIRED_IMPORT_FIELDS = (
    "offer_id",
    "merchant",
    "merchant_id",
    "merchant_name",
    "price",
    "in_stock",
    "product_url",
    "last_updated_at",
    "data_source",
)

IDENTIFIER_FIELDS = (
    "merchant_product_id",
    "ean",
    "gtin",
)

PROMOTION_ASSET_FIELDS = (
    "affiliate_url",
    "image_url",
)


def _non_empty(value: object) -> bool:
    return value is not None and bool(str(value).strip())


def _http_url(value: object) -> bool:
    if not _non_empty(value):
        return False

    parsed = urlparse(str(value).strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _positive_price(value: object) -> bool:
    if isinstance(value, bool):
        return False
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _parseable_timestamp(value: object) -> bool:
    if not _non_empty(value):
        return False

    raw = str(value).strip().replace("Z", "+00:00")
    try:
        datetime.fromisoformat(raw)
    except ValueError:
        return False
    return True


def _parseable_bool(value: object) -> bool:
    if isinstance(value, bool):
        return True

    if isinstance(value, int) and value in {0, 1}:
        return True

    if isinstance(value, str):
        return value.strip().casefold() in {
            "true",
            "false",
            "1",
            "0",
            "yes",
            "no",
        }

    return False


def _row_checks(row: dict) -> dict[str, bool]:
    identifier_ok = any(_non_empty(row.get(field)) for field in IDENTIFIER_FIELDS)

    checks = {
        "offer_id": _non_empty(row.get("offer_id")),
        "merchant": _non_empty(row.get("merchant")),
        "merchant_id": _non_empty(row.get("merchant_id")),
        "merchant_name": _non_empty(row.get("merchant_name")),
        "product_identifier": identifier_ok,
        "price": _positive_price(row.get("price")),
        "in_stock": _parseable_bool(row.get("in_stock")),
        "product_url": _http_url(row.get("product_url")),
        "affiliate_url": _http_url(row.get("affiliate_url")),
        "last_updated_at": _parseable_timestamp(row.get("last_updated_at")),
        "data_source": _non_empty(row.get("data_source")),
        "image_url": _http_url(row.get("image_url")),
    }

    currency = row.get("currency")
    checks["currency"] = _non_empty(currency) and len(str(currency).strip()) == 3

    return checks


def build_feed_preflight(rows: list[dict]) -> dict[str, Any]:
    total = len(rows)

    field_names = [
        "offer_id",
        "merchant",
        "merchant_id",
        "merchant_name",
        "product_identifier",
        "price",
        "currency",
        "in_stock",
        "product_url",
        "affiliate_url",
        "last_updated_at",
        "data_source",
        "image_url",
    ]

    valid_counts = {field: 0 for field in field_names}

    import_ready_rows = 0
    promotion_ready_rows = 0
    issues: list[dict[str, Any]] = []

    required_for_import = {
        "offer_id",
        "merchant",
        "merchant_id",
        "merchant_name",
        "product_identifier",
        "price",
        "currency",
        "in_stock",
        "product_url",
        "last_updated_at",
        "data_source",
    }

    for index, row in enumerate(rows):
        checks = _row_checks(row)

        for field, passed in checks.items():
            if passed:
                valid_counts[field] += 1

        import_failures = sorted(field for field in required_for_import if not checks[field])

        promotion_failures = sorted(
            field for field in ("affiliate_url", "image_url") if not checks[field]
        )

        if not import_failures:
            import_ready_rows += 1

        if not import_failures and not promotion_failures:
            promotion_ready_rows += 1

        if import_failures or promotion_failures:
            issues.append(
                {
                    "row_index": index,
                    "offer_id": row.get("offer_id"),
                    "merchant_product_id": row.get("merchant_product_id"),
                    "import_failures": import_failures,
                    "promotion_failures": promotion_failures,
                }
            )

    coverage = {}
    for field in field_names:
        valid = valid_counts[field]
        coverage[field] = {
            "valid": valid,
            "missing_or_invalid": total - valid,
            "coverage_pct": (round((valid / total) * 100, 1) if total else 0.0),
        }

    ready_for_offer_import = total > 0 and import_ready_rows == total
    ready_for_promotion_assets = total > 0 and promotion_ready_rows == total

    return {
        "row_count": total,
        "import_ready_rows": import_ready_rows,
        "promotion_ready_rows": promotion_ready_rows,
        "ready_for_offer_import": ready_for_offer_import,
        "ready_for_promotion_assets": ready_for_promotion_assets,
        "coverage": coverage,
        "issue_count": len(issues),
        "issues": issues,
    }
