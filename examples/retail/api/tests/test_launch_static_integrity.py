from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from demo_common import REPO_ROOT

RETAIL_ROOT = REPO_ROOT / "examples" / "retail"
DATA_ROOT = RETAIL_ROOT / "data"
PUBLIC_ROOT = RETAIL_ROOT / "storefront-web" / "public"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("’", "").replace("'", "").replace("&", " und ").lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    return normalized.strip("-")


def live_catalog_rows() -> list[dict]:
    catalog = load_json(DATA_ROOT / "catalog.json")
    return [
        product
        for product in catalog.get("products", [])
        if str(product.get("product_id") or "").startswith("SC-")
        and product.get("category") == "fragrance"
        and product.get("in_stock") is not False
    ]


def test_every_live_fragrance_has_source_data_and_local_image() -> None:
    products = live_catalog_rows()
    source = load_json(DATA_ROOT / "scentai_products.json")
    source_by_id = {product["product_id"]: product for product in source.get("products", [])}

    assert products

    for product in products:
        product_id = product["product_id"]
        assert product_id in source_by_id

        image_url = str(product.get("image_url") or "")
        assert image_url.startswith("/products/")

        image_path = PUBLIC_ROOT / image_url.lstrip("/")
        assert image_path.exists(), f"Missing launch image for {product_id}: {image_url}"


def test_live_fragrance_slugs_are_unique() -> None:
    products = live_catalog_rows()
    source = load_json(DATA_ROOT / "scentai_products.json")
    source_by_id = {product["product_id"]: product for product in source.get("products", [])}

    slugs: list[str] = []

    for product in products:
        source_product = source_by_id[product["product_id"]]
        attributes = product.get("attributes") or {}
        brand = str(product.get("brand") or source_product.get("brand") or "").strip()
        name = str(
            attributes.get("canonical_name")
            or source_product.get("name")
            or product.get("title")
            or ""
        ).strip()

        slugs.append(slugify(f"{brand} {name}"))

    assert len(slugs) == len(set(slugs))


def test_analytics_sql_core_sections_are_not_duplicated() -> None:
    sql = (DATA_ROOT / "scentai_analytics_supabase.sql").read_text(encoding="utf-8")

    assert sql.count("create table if not exists public.scentai_analytics_events") == 1
    assert sql.count("create or replace view public.scentai_acquisition_funnel") == 1
    assert sql.count("create or replace view public.scentai_personal_library_engagement") == 1
    assert sql.count("create view public.scentai_catalog_search_demand") == 1
    assert sql.count("alter table public.scentai_analytics_events enable row level security") == 1

    for column in (
        "acquisition_source",
        "campaign_id",
        "content_id",
    ):
        assert column in sql
