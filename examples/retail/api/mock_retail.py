# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The retail example's ``StorefrontBackend`` over the fixtures in ``data/``: keyword
search, per-session carts, fixture orders and policies. An adopter replaces this class
with calls to their own catalog, cart, and order systems."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from demo_common.storefront_fixtures import (
    SessionCarts,
    example_data_dir,
    find_order,
    find_product,
    keyword_score,
    load_catalog,
    load_orders,
    load_policies,
    load_users,
    newest_orders,
    option_text,
    orders_for,
    preferences_of,
    rank_products,
    search_help,
    summary_of,
    unavailable_detail,
    within_price_and_rating,
)
from shopping_agent import (
    Cart,
    FulfillmentOption,
    Order,
    Policy,
    Product,
    ProductDetails,
    SearchFilters,
    ShoppingSessionContext,
    StorefrontBackend,
    Unavailable,
    UserPreferences,
)

DATA_DIR = example_data_dir(__file__)

# Attributes stamped onto products at boot rather than authored in the catalog. The
# merchant side re-stamps LOW_STOCK_ATTRIBUTE when an applied change moves the number.
DELIVERY_ATTRIBUTE = "delivery"
LOW_STOCK_ATTRIBUTE = "low_stock"
_STAMPED_ATTRIBUTES = {DELIVERY_ATTRIBUTE, LOW_STOCK_ATTRIBUTE}

_SEARCH_WEIGHTS = {
    "title": 3.0,
    "brand": 2.0,
    "category": 2.0,
    "attributes": 1.5,
    "description": 1.0,
}
_SYNONYMS: dict[str, list[str]] = {
    "luggage": ["spinner", "carry-on", "suitcase"],
    "suitcase": ["spinner", "carry-on", "luggage"],
    "headphones": ["headphone", "earphones"],
    "computer": ["laptop", "monitor"],
    "workout": ["fitness", "exercise"],
    "exercise": ["fitness", "workout"],
    "puppy": ["dog"],
    "kitten": ["cat"],
    "kid": ["kids", "children"],
    "child": ["kids", "children"],
    "couch": ["sofa"],
    "present": ["gift"],
    "camping": ["camp", "tent", "outdoor"],
    "cook": ["cookware", "kitchen"],
    "coffee": ["espresso"],
    "sleep": ["sleeping"],
    "pack": ["backpack"],
    "hike": ["hiking"],
}

# Review-aspect vocabularies per category (invented, like the reviews themselves).
_ASPECTS_BY_CATEGORY: dict[str, list[str]] = {
    "toys-games": ["Durability", "Play value", "Age fit", "Easy cleanup"],
    "kids-room": ["Easy setup", "Looks as pictured", "Durability", "Kid appeal"],
    "pet-supplies": ["Durability", "Pet comfort", "Easy to clean", "Sizing"],
    "home-kitchen": ["Build quality", "Easy to clean", "Performance", "Value"],
    "office-electronics": ["Build quality", "Setup", "Comfort", "Reliability"],
    "outdoor-camping": ["Weather resistance", "Pack size", "Setup", "Durability"],
    "fitness": ["Build quality", "Grip", "Sizing", "Value"],
    "travel": ["Durability", "Packability", "Wheels & handle", "Capacity"],
    "beauty-personal-care": ["Gentle formula", "Scent", "Results", "Value"],
    "furniture-bedroom": ["Assembly", "Comfort", "Build quality", "As pictured"],
    "grocery": ["Freshness", "Taste", "Packaging", "Value"],
}
_ASPECTS_FALLBACK = ["Quality", "As described", "Value"]
_FREIGHT_CATEGORIES = {"office-electronics", "fitness"}
_FREIGHT_PRICE_FLOOR = 350
# The terms of the shipping entry in policies.json, which is what the agent quotes;
# test_mock_retail checks that the entry still states each of them.
FREE_SHIPPING_OVER = 49
STANDARD_SHIPPING = FulfillmentOption(
    method="delivery", eta="3-5 business days (standard)", fee=5.99
)
EXPRESS_SHIPPING = FulfillmentOption(method="delivery", eta="2 business days (express)", fee=9.99)
FREIGHT_SHIPPING = FulfillmentOption(method="shipping", eta="5-7 business days (freight)", fee=29.0)
_STORE_OPENS, _STORE_CLOSES = 9, 21


class MockRetail(StorefrontBackend):
    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        catalog, self.products, self.variants = load_catalog(data_dir)
        self.store_name: str = catalog.get("store_name", "the store")
        self._users = load_users(data_dir)
        self._orders = load_orders(data_dir)
        self._policies = load_policies(data_dir)
        self._carts = SessionCarts()
        self._stamp_delivery_promises()
        self._stamp_low_stock(data_dir)

    def _stamp_delivery_promises(self) -> None:
        """A "Get it by <day>" attribute on every in-stock product: boot date plus a
        stable 2-4 day offset per product, never a Sunday, so promises stay current and
        a product's promise is the same for the whole run."""
        boot = datetime.now()
        for product in self.products.values():
            if not product.in_stock:
                continue
            promised = boot + timedelta(days=2 + sum(ord(ch) for ch in product.product_id) % 3)
            if promised.weekday() == 6:
                promised += timedelta(days=1)
            label = f"Get it by {promised.strftime('%a, %b')} {promised.day}"
            product.attributes[DELIVERY_ATTRIBUTE] = label
            # A family's in-stock variants ship on the family's promise.
            for variant in product.variants:
                if (record := self.variants.get(variant.product_id)) and record.in_stock:
                    record.attributes[DELIVERY_ATTRIBUTE] = label

    def _stamp_low_stock(self, data_dir: Path) -> None:
        """The "only N left" attribute, taken from the same inventory rows the merchant
        portal shows, so the storefront's scarcity chip and the portal agree."""
        overlay_path = data_dir / "merchant_inventory.json"
        if not overlay_path.exists():
            return
        overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
        default_threshold = int(overlay.get("default_threshold", 8))
        for row in overlay.get("inventory", []):
            product = self.product(row.get("product_id", ""))
            if product is None or not product.in_stock:
                continue
            stock = int(row.get("stock", 0))
            if 0 < stock <= int(row.get("threshold", default_threshold)):
                product.attributes[LOW_STOCK_ATTRIBUTE] = str(stock)

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    def listing_of(self, product_id: str) -> ProductDetails | None:
        """The listing an id belongs to: itself, or its family when it is a variant."""
        record = self.product(product_id)
        if record is not None and record.variant_of:
            return self.products.get(record.variant_of)
        return record

    def _searchable_text(self, product: ProductDetails) -> dict[str, str]:
        return {
            "title": product.title,
            "brand": product.brand or "",
            "category": product.category or "",
            "attributes": " ".join(
                f"{k} {v}" for k, v in product.attributes.items() if k not in _STAMPED_ATTRIBUTES
            )
            + " "
            + option_text(product),
            "description": f"{product.short_description or ''} {product.long_description or ''}",
        }

    @staticmethod
    def _customer_facing_product(
        product,
        reference_name: str | None = None,
    ):
        """Return SCENTAI data without internal implementation fields."""

        if not product.product_id.startswith("SC-"):
            return product

        source_attributes = product.attributes or {}

        relationship = source_attributes.get(
            "relationship_role"
        )

        internal_attributes = {
            "canonical_name",
            "cluster_id",
            "relationship_role",
            "evidence_confidence",
            "trend_bet",
            "similar_to",
        }

        attributes = {
            key: value
            for key, value in source_attributes.items()
            if key not in internal_attributes
        }

        short_description = product.short_description or ""

        if reference_name:
            if relationship == "clone":
                relation_text = (
                    f"Very close in scent direction to "
                    f"{reference_name}."
                )

            elif relationship == "inspired":
                relation_text = (
                    f"Clearly follows a similar scent direction "
                    f"to {reference_name}, while keeping its "
                    f"own character."
                )

            elif relationship == "alternative":
                relation_text = (
                    f"Offers a related scent style to "
                    f"{reference_name}, with noticeable "
                    f"differences."
                )

            elif relationship == "benchmark":
                relation_text = (
                    f"A reference fragrance in a closely "
                    f"related scent direction to "
                    f"{reference_name}."
                )

            else:
                relation_text = (
                    f"Recommended as a fragrance alternative "
                    f"to {reference_name}."
                )

            short_description = (
                f"{relation_text} {short_description}"
            ).strip()

        return product.model_copy(
            update={
                "attributes": attributes,
                "short_description": short_description,
            }
        )

    def _score(self, product: ProductDetails, query_tokens: list[str]) -> float:
        return keyword_score(
            self._searchable_text(product), _SEARCH_WEIGHTS, query_tokens, _SYNONYMS
        )

    @staticmethod
    def _soft_filter(product: ProductDetails, filters: SearchFilters) -> bool:
        if filters.category and filters.category.lower() not in (product.category or "").lower():
            return False
        if not filters.attributes:
            return True
        haystack = " ".join(
            f"{k}={v}".lower()
            for k, v in product.attributes.items()
            if k not in _STAMPED_ATTRIBUTES
        )
        haystack += f" {product.title.lower()} {option_text(product).lower()}"
        return all(str(value).lower() in haystack for value in filters.attributes.values())

    async def search_products(
        self,
        session: ShoppingSessionContext,
        query: str,
        filters: SearchFilters | None = None,
        limit: int = 8,
    ) -> list[Product]:
        del session

        products = list(self.products.values())

        # SCENTAI cluster-aware alternative search.
        #
        # If the shopper explicitly asks for alternatives to a named
        # benchmark, prioritize products from that benchmark's cluster.
        query_lower = query.casefold()

        def normalize_search_text(value: str) -> str:
            normalized = unicodedata.normalize(
                "NFKD",
                value.casefold(),
            )
            normalized = "".join(
                char
                for char in normalized
                if not unicodedata.combining(char)
            )

            for separator in ("-", "/", "'", "’"):
                normalized = normalized.replace(
                    separator,
                    " ",
                )

            return " ".join(normalized.split())

        normalized_query = normalize_search_text(query)
        query_tokens = set(normalized_query.split())

        alternative_markers = (
            "alternative",
            "alternativen",
            "dupe",
            "dupes",
            "clone",
            "clones",
            "similar",
            "similar to",
            "ähnlich",
            "ersatz",
            "instead",
        )

        asks_for_alternative = any(
            marker in query_lower
            for marker in alternative_markers
        )

        if asks_for_alternative:
            benchmark_matches = []

            for candidate in products:
                attributes = candidate.attributes or {}

                if attributes.get("relationship_role") != "benchmark":
                    continue

                canonical_name = str(
                    attributes.get("canonical_name") or ""
                ).strip()

                cluster_id = attributes.get("cluster_id")

                normalized_name = normalize_search_text(
                    canonical_name
                )

                normalized_brand = normalize_search_text(
                    candidate.brand or ""
                )

                ignored_name_tokens = {
                    "eau",
                    "de",
                    "parfum",
                    "le",
                    "gemme",
                    "parfums",
                    "perfumes",
                }

                name_tokens = [
                    token
                    for token in normalized_name.split()
                    if token not in ignored_name_tokens
                ]

                brand_tokens = [
                    token
                    for token in normalized_brand.split()
                    if token not in {
                        "parfums",
                        "perfumes",
                        "de",
                    }
                ]

                matched_name_tokens = [
                    token
                    for token in name_tokens
                    if token in query_tokens
                ]

                exact_name_match = (
                    normalized_name
                    and normalized_name in normalized_query
                )

                brand_match = any(
                    token in query_tokens
                    for token in brand_tokens
                )

                if (
                    canonical_name
                    and cluster_id
                    and matched_name_tokens
                    and (
                        exact_name_match
                        or brand_match
                        or len(name_tokens) == 1
                    )
                ):
                    benchmark_matches.append(
                        (
                            len(matched_name_tokens),
                            exact_name_match,
                            brand_match,
                            len(name_tokens),
                            candidate.product_id,
                            cluster_id,
                        )
                    )

            if benchmark_matches:
                # Prefer the longest matching benchmark name.
                # This ensures "Absolu Aventus" wins over "Aventus".
                benchmark_matches.sort(
                    key=lambda item: (
                        item[0],
                        item[1],
                        item[2],
                        item[3],
                    ),
                    reverse=True,
                )

                target_anchor_id = benchmark_matches[0][4]
                target_cluster = benchmark_matches[0][5]

                target_anchor = next(
                    (
                        product
                        for product in products
                        if product.product_id == target_anchor_id
                    ),
                    None,
                )

                reference_name = ""

                if target_anchor is not None:
                    anchor_attributes = (
                        target_anchor.attributes or {}
                    )

                    anchor_name = str(
                        anchor_attributes.get(
                            "canonical_name"
                        )
                        or target_anchor.title
                    ).strip()

                    reference_name = " ".join(
                        part
                        for part in (
                            target_anchor.brand,
                            anchor_name,
                        )
                        if part
                    )

                same_cluster_products = [
                    product
                    for product in products
                    if (
                        (product.attributes or {}).get("cluster_id")
                        == target_cluster
                        and
                        product.product_id != target_anchor_id
                    )
                ]

                ranked_cluster = rank_products(
                    same_cluster_products,
                    query,
                    filters,
                    limit,
                    score=self._score,
                    hard_filter=within_price_and_rating,
                    soft_filter=self._soft_filter,
                )

                if ranked_cluster:
                    return [
                        self._customer_facing_product(
                            summary_of(product),
                            reference_name=reference_name,
                        )
                        for product in ranked_cluster
                    ]

        # Normal storefront search fallback.
        ranked = rank_products(
            products,
            query,
            filters,
            limit,
            score=self._score,
            hard_filter=within_price_and_rating,
            soft_filter=self._soft_filter,
        )

        return [
            self._customer_facing_product(
                summary_of(product)
            )
            for product in ranked
        ]

    def product(self, product_id: str) -> ProductDetails | None:
        return find_product(self.products, self.variants, product_id)

    async def get_product_details(
        self, session: ShoppingSessionContext, product_id: str
    ) -> ProductDetails | None:
        del session
        product = self.product(product_id)

        if product is None:
            return None

        return self._customer_facing_product(product)

    def price_intelligence(self, product_id: str) -> dict[str, Any] | None:
        """A 90-day price series derived from the product id, ending at today's price,
        with a verdict computed from where that price sits in the series' range. Read
        by the storefront's detail panel; the agent never sees it."""
        product = self.product(product_id)
        if product is None or product.price <= 0:
            return None
        digest = hashlib.sha256(product_id.encode("utf-8")).digest()
        amplitude = product.price * (0.06 + (digest[0] / 255) * 0.08)
        phase = (digest[1] / 255) * 2 * math.pi
        drift = ((digest[2] / 255) - 0.5) * 0.5
        points = 13
        series = []
        for i in range(points):
            wobble = math.sin(phase + i * 1.1) + 0.4 * math.sin(phase * 2 + i * 2.3)
            trend = drift * (i - points + 1) / points
            series.append(round(max(product.price + amplitude * (wobble / 1.4 + trend), 0.5), 2))
        series[-1] = product.price
        low, high = min(series), max(series)
        if high - low < 0.01:
            position = "typical"
        else:
            ratio = (product.price - low) / (high - low)
            position = "low" if ratio <= 0.25 else "high" if ratio >= 0.75 else "typical"
        verdict = {
            "low": f"${product.price:.2f} is near this item's 90-day low",
            "typical": f"${product.price:.2f} is this item's typical price",
            "high": f"${product.price:.2f} is above this item's typical price",
        }[position]
        return {
            "days": 90,
            "series": series,
            "low": low,
            "high": high,
            "position": position,
            "verdict": f"{verdict} (90-day range ${low:.0f}–${high:.0f})",
        }

    def review_aspects(self, product_id: str) -> dict[str, Any] | None:
        """Review-aspect chips derived from the product id, with sentiment anchored to
        its rating and mention counts bounded by its review count. Detail panel only."""
        product = self.listing_of(product_id)
        if product is None or not product.review_count or product.review_count < 25:
            return None
        digest = hashlib.sha256(f"aspects:{product.product_id}".encode()).digest()
        names = _ASPECTS_BY_CATEGORY.get(product.category or "", _ASPECTS_FALLBACK)
        count = 3 if len(names) < 4 or digest[0] % 2 == 0 else 4
        rating = product.rating or 4.2
        mention_share = 0.32 + (digest[1] / 255) * 0.2
        aspects = []
        for i, name in enumerate(names[:count]):
            jitter = (digest[2 + i] / 255 - 0.5) * 14
            positive_pct = round(min(97.0, max(45.0, rating * 20 - 4 + jitter - i * 3)))
            share = mention_share * (0.45 if i == 0 else 0.55 / max(count - 1, 1))
            floor = min(12, product.review_count // (count + 1))
            mentions = max(int(product.review_count * share), floor, 1)
            aspects.append({"name": name, "positive_pct": int(positive_pct), "mentions": mentions})
        return {"review_count": product.review_count, "aspects": aspects}

    # ------------------------------------------------------------------
    # Cart
    # ------------------------------------------------------------------

    async def get_cart(self, session: ShoppingSessionContext) -> Cart:
        return self._carts.cart(session.session_id)

    async def add_to_cart(
        self, session: ShoppingSessionContext, product_id: str, quantity: int
    ) -> Cart:
        product = self.product(product_id)
        if product is None or product.has_options:
            # The executor's gates hold both cases before they reach a backend; a real
            # cart service refuses them on its own terms too.
            raise KeyError(product_id)
        if not product.in_stock:
            raise Unavailable(unavailable_detail(product, self.listing_of(product_id)))
        existing = self._carts.lines(session.session_id).get(product_id)
        quantity += existing.quantity if existing else 0
        return self._carts.put(session.session_id, product, quantity)

    async def update_cart_item(
        self, session: ShoppingSessionContext, product_id: str, quantity: int
    ) -> Cart:
        return self._carts.set_quantity(session.session_id, product_id, quantity)

    async def remove_from_cart(self, session: ShoppingSessionContext, product_id: str) -> Cart:
        return self._carts.remove(session.session_id, product_id)

    def reset_session(self, session_id: str) -> None:
        self._carts.reset(session_id)

    # ------------------------------------------------------------------
    # Customer, orders, help content, fulfillment
    # ------------------------------------------------------------------

    async def get_preferences(self, session: ShoppingSessionContext) -> UserPreferences:
        return preferences_of(self._users, session.user_id)

    async def get_orders(self, session: ShoppingSessionContext, limit: int = 5) -> list[Order]:
        return orders_for(self._orders, session.user_id, limit)

    async def get_order(self, session: ShoppingSessionContext, order_id: str) -> Order | None:
        return find_order(self._orders, session.user_id, order_id)

    def recent_orders(self, limit: int = 6) -> list[Order]:
        return newest_orders(self._orders, limit)

    async def search_policies(self, session: ShoppingSessionContext, query: str) -> list[Policy]:
        del session
        return search_help(self._policies, query)

    @staticmethod
    def _pickup_eta(now: datetime) -> str:
        """Two hours of preparation from now (or from opening), promised as the top of
        an hour inside store hours, otherwise tomorrow morning."""
        opens = now.replace(hour=_STORE_OPENS, minute=0, second=0, microsecond=0)
        ready = max(now, opens) + timedelta(hours=2)
        if ready.minute or ready.second or ready.microsecond:
            ready = ready.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        if ready.date() != now.date() or ready.hour > _STORE_CLOSES:
            return "tomorrow morning"
        hour12 = ready.hour % 12 or 12
        return f"today by {hour12} {'AM' if ready.hour < 12 else 'PM'}"

    async def get_fulfillment_options(
        self, session: ShoppingSessionContext, product_ids: list[str]
    ) -> list[FulfillmentOption]:
        prefs = await self.get_preferences(session)
        location = prefs.default_location or "your area"
        quoted = [product for pid in product_ids if (product := self.product(pid))]
        standard = STANDARD_SHIPPING
        if sum(product.price for product in quoted) > FREE_SHIPPING_OVER:
            standard = standard.model_copy(update={"fee": 0.0})
        options = [
            standard,
            EXPRESS_SHIPPING,
            FulfillmentOption(
                method="pickup",
                eta=self._pickup_eta(datetime.now()),
                fee=0.0,
                location=f"ACME {location}",
            ),
        ]
        if any(
            product.category in _FREIGHT_CATEGORIES and product.price > _FREIGHT_PRICE_FLOOR
            for product in quoted
        ):
            options.append(FREIGHT_SHIPPING)
        return options
