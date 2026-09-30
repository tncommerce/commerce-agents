"""Read-only storefront inventory and audience gaps for catalog planning."""

from __future__ import annotations

from collections import Counter
from typing import Any

from scripts.report_scentai_merchant_coverage import storefront_audience


def visible_inventory(
    catalog: dict[str, Any], source: dict[str, Any] | None = None
) -> tuple[list[str], list[str], Counter[str]]:
    source_by_id = {row["product_id"]: row for row in (source or {}).get("products", [])}
    visible: list[str] = []
    hidden: list[str] = []
    counts: Counter[str] = Counter()
    for product in catalog.get("products", []):
        product_id = str(product.get("product_id") or "")
        if (
            not product_id.startswith("SC-")
            or product.get("category") != "fragrance"
            or product.get("in_stock") is False
        ):
            continue
        original = source_by_id.get(product_id, {})
        blockers = (original.get("validation") or {}).get("blockers", [])
        if isinstance(blockers, list) and any(str(value or "").strip() for value in blockers):
            hidden.append(product_id)
            continue
        visible.append(product_id)
        groups = (original.get("classification") or {}).get("scentai_target_groups")
        if not groups:
            raw = str((product.get("attributes") or {}).get("target_group") or "")
            groups = [value.strip() for value in raw.split(",") if value.strip()]
        audience = storefront_audience(groups)
        if audience:
            counts[audience] += 1
    return visible, hidden, counts


def storefront_gap_score(target_groups: list[str], counts: Counter[str]) -> float:
    audience = storefront_audience(target_groups)
    if audience is None:
        return 0.0
    maximum = max(counts.values(), default=0)
    if maximum <= 0:
        return 10.0
    return round(min(10.0, max(0, maximum - counts[audience]) / maximum * 10.0), 2)
