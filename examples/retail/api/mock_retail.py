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
from difflib import SequenceMatcher
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

from .merchant_offers import MerchantOfferStore, offer_total_price

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
    def __init__(
        self,
        data_dir: Path = DATA_DIR,
        offer_store: MerchantOfferStore | None = None,
    ) -> None:
        catalog, self.products, self.variants = load_catalog(data_dir)
        self.offer_store = offer_store
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

    def _with_commerce_price(self, product: ProductDetails) -> ProductDetails:
        """Stamp the best current merchant price onto SCENTAI products.

        Products with an eligible live merchant offer use that customer total as the
        effective price. Products without one retain the catalog market reference and
        are explicitly marked so the agent/UI do not present it as a live buy price.
        """

        if not product.product_id.startswith("SC-"):
            return product

        attributes = dict(product.attributes or {})
        offers = self.offer_store.offers_for(product.product_id) if self.offer_store else []

        if offers:
            best_offer = offers[0]
            customer_total = offer_total_price(best_offer)
            effective_price = customer_total if customer_total is not None else best_offer.price
            attributes.update(
                {
                    "price_source": "current_merchant_offer",
                    "price_merchant": best_offer.merchant_name,
                    "merchant_price_checked_at": best_offer.last_updated_at.isoformat(),
                }
            )
            return product.model_copy(
                update={
                    "price": effective_price,
                    "attributes": attributes,
                }
            )

        attributes["price_source"] = "market_reference"
        return product.model_copy(update={"attributes": attributes})

    def customer_product(self, product_id: str) -> ProductDetails | None:
        product = self.product(product_id)
        if product is None:
            return None
        return self._customer_facing_product(product)

    def _customer_facing_product(
        self,
        product,
        reference_name: str | None = None,
        reference_accords: str | None = None,
        query_text: str | None = None,
    ):
        """Return SCENTAI data without internal implementation fields."""
        product = self._with_commerce_price(product)

        if not product.product_id.startswith("SC-"):
            return product

        source_attributes = product.attributes or {}

        relationship = source_attributes.get("relationship_role")

        internal_attributes = {
            "canonical_name",
            "cluster_id",
            "relationship_role",
            "evidence_confidence",
            "trend_bet",
            "similar_to",
            "relationship_links",
            "freshness",
            "sweetness",
            "woodiness",
            "spiciness",
        }

        attributes = {
            key: value for key, value in source_attributes.items() if key not in internal_attributes
        }

        accord_labels_de = {
            "sweet": "süß",
            "spicy": "würzig",
            "gourmand": "gourmandig",
            "creamy": "cremig",
            "oriental": "orientalisch",
            "citrus": "zitrisch",
            "fresh": "frisch",
            "woody": "holzig",
            "floral": "blumig",
            "fruity": "fruchtig",
            "aquatic": "aquatisch",
            "powdery": "pudrig",
            "smoky": "rauchig",
            "green": "grün",
            "aromatic": "aromatisch",
            "synthetic": "synthetisch",
            "leathery": "ledrig",
            "resinous": "harzig",
            "chypre": "chypre",
            "white floral": "weiße Blüten",
        }

        if attributes.get("main_accords"):
            attributes["main_accords"] = ", ".join(
                accord_labels_de.get(
                    accord.strip().casefold(),
                    accord.strip(),
                )
                for accord in str(attributes["main_accords"]).split(",")
                if accord.strip()
            )

        def scent_profile_level(name: str) -> str | None:
            try:
                value = source_attributes.get(name)
                if value in (None, ""):
                    return None

                score = float(value)
            except (TypeError, ValueError):
                return None

            if score <= 4:
                return "niedrig"
            if score <= 6:
                return "mittel"
            return "hoch"

        profile_labels = (
            ("freshness", "Frische"),
            ("sweetness", "Süße"),
            ("woodiness", "Holzigkeit"),
            ("spiciness", "Würze"),
        )

        profile_parts = []

        for key, label in profile_labels:
            level = scent_profile_level(key)

            if level is not None:
                profile_parts.append(f"{label}: {level}")

        if profile_parts:
            attributes["duftprofil_intensitaet"] = ", ".join(profile_parts)

        canonical_name = str(source_attributes.get("canonical_name") or product.title).strip()
        concentration = str(source_attributes.get("concentration") or "").strip()
        translated_accords = [
            accord.strip()
            for accord in str(attributes.get("main_accords") or "").split(",")
            if accord.strip()
        ]

        description_parts = [
            " ".join(
                part
                for part in (
                    product.brand,
                    canonical_name,
                )
                if part
            ).strip(),
            concentration,
        ]
        if translated_accords:
            description_parts.append("Duftprofil: " + ", ".join(translated_accords[:3]))

        short_description = " · ".join(part for part in description_parts if part)
        if short_description:
            short_description += "."

        if reference_name:
            if relationship == "clone":
                relation_text = f"Sehr nah an der Duftrichtung von {reference_name}."

            elif relationship == "inspired":
                relation_text = (
                    f"Orientiert sich klar an einer ähnlichen "
                    f"Duftrichtung wie {reference_name}, behält "
                    f"aber einen eigenen Charakter."
                )

            elif relationship == "alternative":
                relation_text = (
                    f"Bietet eine verwandte Duftrichtung zu "
                    f"{reference_name}, mit erkennbaren "
                    f"Unterschieden."
                )

            elif relationship == "benchmark":
                relation_text = (
                    f"Referenzduft innerhalb einer eng verwandten Duftrichtung zu {reference_name}."
                )

            else:
                relation_text = f"Als Duftalternative zu {reference_name} eingeordnet."

            short_description = (f"{relation_text} {short_description}").strip()

        if reference_accords:
            translated_reference_accords = ", ".join(
                accord_labels_de.get(
                    accord.strip().casefold(),
                    accord.strip(),
                )
                for accord in reference_accords.split(",")
                if accord.strip()
            )
            short_description = (
                f"{short_description} "
                f"Der Referenzduft ist im Katalog mit diesen Akkorden "
                f"hinterlegt: {translated_reference_accords}."
            ).strip()

        query_fit = self._query_fit_signals(
            product,
            query_text or "",
        )
        if query_fit:
            attributes["anfrage_passung"] = ", ".join(query_fit)
        internal_labels = {
            "benchmark",
            "clone",
            "inspired",
            "alternative",
        }

        customer_labels = [
            label
            for label in (product.labels or [])
            if str(label).casefold() not in internal_labels
        ]

        return product.model_copy(
            update={
                "attributes": attributes,
                "labels": customer_labels,
                "short_description": short_description,
            }
        )

    @staticmethod
    def _query_fit_signals(
        product: ProductDetails,
        query_text: str,
    ) -> list[str]:
        """Return conservative, evidence-backed fit labels for the current query."""

        if not query_text:
            return []

        normalized = unicodedata.normalize(
            "NFKD",
            query_text.casefold(),
        )
        normalized = "".join(
            char for char in normalized if not unicodedata.combining(char)
        ).replace("ß", "ss")
        normalized = " ".join(normalized.split())

        attributes = product.attributes or {}

        def number(name: str) -> float | None:
            try:
                value = attributes.get(name)
                if value in (None, ""):
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None

        freshness = number("freshness")
        sweetness = number("sweetness")
        woodiness = number("woodiness")
        spiciness = number("spiciness")
        longevity = number("longevity")
        projection = number("projection")

        signals: list[str] = []

        wants_summer = any(
            term in normalized
            for term in (
                "sommer",
                "summer",
                "heiss",
                "hitze",
                "warmes wetter",
            )
        )
        wants_winter = any(
            term in normalized
            for term in (
                "winter",
                "kalte tage",
                "kaltes wetter",
                "cold weather",
            )
        )
        wants_spring = any(
            term in normalized
            for term in (
                "fruhling",
                "spring",
            )
        )
        wants_autumn = any(
            term in normalized
            for term in (
                "herbst",
                "autumn",
                "fall",
            )
        )
        wants_office = any(
            term in normalized
            for term in (
                "buro",
                "office",
                "business",
            )
        )
        wants_date = any(
            term in normalized
            for term in (
                "date",
                "date night",
                "abend",
                "evening",
                "romantisch",
            )
        )
        wants_party = any(
            term in normalized
            for term in (
                "party",
                "club",
                "feiern",
                "nightlife",
            )
        )
        avoids_sweet = any(
            phrase in normalized
            for phrase in (
                "nicht zu suss",
                "nicht suss",
                "wenig suss",
                "not too sweet",
                "low sweetness",
            )
        )
        wants_longevity = any(
            term in normalized
            for term in (
                "haltbarkeit",
                "lange haltbarkeit",
                "long lasting",
                "long-lasting",
                "longevity",
                "lasting",
            )
        )
        wants_projection = any(
            term in normalized
            for term in (
                "ausstrahlung",
                "projection",
                "sillage",
                "auffallig",
                "noticeable",
                "strong projection",
            )
        )

        if (
            wants_summer
            and freshness is not None
            and sweetness is not None
            and freshness >= 8
            and sweetness <= 6
        ):
            signals.append("frisches Sommerprofil")

        if wants_winter:
            warm_values = [
                value
                for value in (
                    sweetness,
                    woodiness,
                    spiciness,
                )
                if value is not None
            ]
            if warm_values and sum(warm_values) / len(warm_values) >= 6:
                signals.append("warmes Winterprofil")

        accords = str(attributes.get("main_accords") or "").casefold()

        if (
            wants_spring
            and freshness is not None
            and freshness >= 7
            and any(
                accord in accords
                for accord in (
                    "floral",
                    "fruity",
                    "green",
                    "citrus",
                    "fresh",
                )
            )
        ):
            signals.append("frisches Frühlingsprofil")

        if wants_autumn:
            warm_values = [
                value
                for value in (
                    sweetness,
                    woodiness,
                    spiciness,
                )
                if value is not None
            ]
            if (
                warm_values
                and sum(warm_values) / len(warm_values) >= 5.5
                and longevity is not None
                and longevity >= 7.2
            ):
                signals.append("warmes Herbstprofil")

        if (
            wants_office
            and all(
                value is not None
                for value in (
                    freshness,
                    sweetness,
                    projection,
                )
            )
            and freshness >= 6
            and sweetness <= 5
            and projection <= 7.5
        ):
            signals.append("ausgewogenes Büroprofil")

        if wants_date and longevity is not None:
            warm_values = [
                value
                for value in (
                    sweetness,
                    woodiness,
                    spiciness,
                )
                if value is not None
            ]
            if warm_values and longevity >= 7.5 and max(warm_values) >= 7:
                signals.append("starkes Abendprofil")

        if (
            wants_party
            and projection is not None
            and longevity is not None
            and projection >= 7.8
            and longevity >= 7.8
        ):
            signals.append("starke Präsenz für Party oder Club")

        wants_everyday = any(
            term in normalized
            for term in (
                "alltag",
                "taglich",
                "daily",
                "everyday",
            )
        )
        if (
            wants_everyday
            and all(
                value is not None
                for value in (
                    freshness,
                    sweetness,
                    projection,
                    longevity,
                )
            )
            and freshness >= 5
            and sweetness <= 7
            and 6.0 <= projection <= 7.8
            and longevity >= 7.0
        ):
            signals.append("ausgewogenes Alltagsprofil")

        if avoids_sweet and sweetness is not None and sweetness <= 4:
            signals.append("geringe Süße")

        if wants_longevity and longevity is not None and longevity >= 7.8:
            signals.append("starke Haltbarkeit")

        if wants_projection and projection is not None and projection >= 7.8:
            signals.append("starke Ausstrahlung")

        return signals[:4]

    @staticmethod
    def _relationship_to_anchor(
        product: ProductDetails,
        anchor_id: str,
    ) -> tuple[str, str] | None:
        """Return (relationship_type, confidence) for an explicit anchor link."""

        raw_links = str((product.attributes or {}).get("relationship_links") or "")

        for raw_link in raw_links.split(";"):
            parts = raw_link.split("|")

            if len(parts) != 3:
                continue

            related_id, relationship_type, confidence = parts

            if related_id == anchor_id:
                return relationship_type, confidence

        return None

    def _alternative_score(
        self,
        product: ProductDetails,
        query_tokens: list[str],
        query_text: str,
        anchor_id: str,
    ) -> float:
        """Rank named-fragrance alternatives by relevance plus evidence quality.

        The explicit relationship to the named reference is the strongest signal.
        Community volume is a smaller confidence signal so a tiny rating edge does
        not outrank a much better-established alternative.
        """

        score = self._score(
            product,
            query_tokens,
            query_text,
        )

        relationship = self._relationship_to_anchor(
            product,
            anchor_id,
        )

        if relationship is not None:
            relationship_type, confidence = relationship

            confidence_bonus = {
                "high": 4.0,
                "medium_high": 3.2,
                "medium": 2.4,
                "low": 1.0,
            }.get(confidence, 0.0)

            relationship_bonus = {
                "clone": 2.0,
                "inspired": 1.5,
                "alternative": 1.2,
            }.get(relationship_type, 0.8)

            score += confidence_bonus + relationship_bonus

        review_count = max(int(product.review_count or 0), 0)
        score += math.log10(review_count + 1) * 0.45

        return score

    def _score(
        self, product: ProductDetails, query_tokens: list[str], query_text: str | None = None
    ) -> float:
        base_score = keyword_score(
            self._searchable_text(product),
            _SEARCH_WEIGHTS,
            query_tokens,
            _SYNONYMS,
        )

        # Keep non-SCENTAI demo products unchanged.
        if not str(product.product_id).startswith("SC-"):
            return base_score

        attributes = product.attributes or {}

        def numeric_attribute(name: str) -> float | None:
            try:
                value = attributes.get(name)
                if value in (None, ""):
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None

        query_text = (
            query_text if query_text is not None else " ".join(str(token) for token in query_tokens)
        ).casefold()

        def normalize_name_text(value: str) -> str:
            normalized = unicodedata.normalize("NFKD", value.casefold())
            normalized = "".join(
                char for char in normalized if not unicodedata.combining(char)
            ).replace("ß", "ss")
            for separator in ("-", "/", "'", "’"):
                normalized = normalized.replace(separator, " ")
            return " ".join(normalized.split())

        def fuzzy_name_bonus() -> float:
            """Reward likely named-fragrance matches even with small typos.

            This is deliberately conservative: it only looks at the canonical fragrance
            name and brand, ignores generic shopping words, and requires strong token
            similarity. It helps queries such as "Para L homme" resolve to
            "Prada L'Homme" without turning general scent requests into fuzzy matches.
            """

            stopwords = {
                "zeig",
                "zeige",
                "mir",
                "bitte",
                "suche",
                "such",
                "ich",
                "den",
                "die",
                "das",
                "einen",
                "eine",
                "ein",
                "duft",
                "parfum",
                "fragrance",
                "von",
                "für",
                "fuer",
                "the",
                "a",
                "an",
                "show",
                "me",
                "find",
            }

            normalized_query = normalize_name_text(query_text)
            query_words = [
                word
                for word in normalized_query.split()
                if word not in stopwords and len(word) >= 2
            ]
            if not query_words:
                return 0.0

            canonical_name = str(attributes.get("canonical_name") or "").strip()
            brand = str(product.brand or "").strip()

            variants = [
                normalize_name_text(canonical_name),
                normalize_name_text(f"{brand} {canonical_name}".strip()),
            ]

            best_score = 0.0

            for variant in variants:
                candidate_words = [
                    word
                    for word in variant.split()
                    if len(word) >= 2 and word not in {"eau", "de", "parfum", "toilette", "extrait"}
                ]
                if not candidate_words:
                    continue

                token_scores = []
                for candidate_word in candidate_words:
                    token_scores.append(
                        max(
                            SequenceMatcher(None, candidate_word, query_word).ratio()
                            for query_word in query_words
                        )
                    )

                strong_matches = [score for score in token_scores if score >= 0.80]
                coverage = len(strong_matches) / len(candidate_words)

                if len(candidate_words) == 1:
                    local_score = strong_matches[0] if strong_matches else 0.0
                elif coverage >= 0.67:
                    local_score = sum(strong_matches) / len(strong_matches)
                else:
                    local_score = 0.0

                best_score = max(best_score, local_score)

            if best_score >= 0.92:
                return 7.0
            if best_score >= 0.86:
                return 5.0
            if best_score >= 0.80:
                return 3.0
            return 0.0

        freshness = numeric_attribute("freshness")
        sweetness = numeric_attribute("sweetness")
        woodiness = numeric_attribute("woodiness")
        spiciness = numeric_attribute("spiciness")
        projection = numeric_attribute("projection")

        accords = str(attributes.get("main_accords") or "").casefold()

        preference_score = fuzzy_name_bonus()

        target_groups = {
            part.strip()
            for part in str(attributes.get("target_group") or "").casefold().split(",")
            if part.strip()
        }
        audience_lean = str(attributes.get("audience_lean") or "").casefold()

        wants_women = any(
            phrase in query_text
            for phrase in (
                "damenduft",
                "damen parfum",
                "damenparfum",
                "für frauen",
                "fuer frauen",
                "für eine frau",
                "fuer eine frau",
                "women",
                "woman",
                "female",
            )
        )
        wants_men = any(
            phrase in query_text
            for phrase in (
                "herrenduft",
                "herren parfum",
                "herrenparfum",
                "für männer",
                "fuer maenner",
                "für einen mann",
                "fuer einen mann",
                "men's",
                "mens",
                "male",
            )
        )
        wants_unisex = "unisex" in query_text
        wants_feminine = any(
            term in query_text for term in ("feminin", "feminine", "weiblich", "female leaning")
        )

        if wants_women:
            if "women" in target_groups:
                preference_score += 4.0
            elif "unisex" in target_groups:
                preference_score += 1.5
            elif "men" in target_groups:
                preference_score -= 3.0

        if wants_men:
            if "men" in target_groups:
                preference_score += 4.0
            elif "unisex" in target_groups:
                preference_score += 1.5
            elif "women" in target_groups:
                preference_score -= 3.0

        if wants_unisex:
            if "unisex" in target_groups:
                preference_score += 3.0
            else:
                preference_score -= 1.0

        if wants_feminine:
            if audience_lean == "feminine":
                preference_score += 3.0
            elif "women" in target_groups:
                preference_score += 2.5
            elif "unisex" in target_groups:
                preference_score += 1.0
            elif audience_lean == "masculine":
                preference_score -= 2.0

        wants_fresh = any(term in query_text for term in ("frisch", "fresh", "sauber", "clean"))

        if wants_fresh and freshness is not None:
            preference_score += (freshness / 10.0) * 3.0

        avoids_sweet = any(
            phrase in query_text
            for phrase in (
                "nicht zu süß",
                "nicht süß",
                "wenig süß",
                "nicht zu suess",
                "nicht suess",
                "not too sweet",
                "low sweetness",
            )
        )

        if avoids_sweet and sweetness is not None:
            preference_score += ((10.0 - sweetness) / 10.0) * 5.0

            if sweetness >= 7:
                preference_score -= 2.0

        wants_sweet = not avoids_sweet and any(
            term in query_text for term in ("süß", "suess", "sweet")
        )

        if wants_sweet and sweetness is not None:
            preference_score += (sweetness / 10.0) * 3.0

        if (
            any(term in query_text for term in ("holzig", "holz", "woody"))
            and woodiness is not None
        ):
            preference_score += (woodiness / 10.0) * 2.5

        if (
            any(term in query_text for term in ("würzig", "wuerzig", "spicy"))
            and spiciness is not None
        ):
            preference_score += (spiciness / 10.0) * 2.5

        wants_discreet = any(
            phrase in query_text
            for phrase in (
                "nicht zu aufdringlich",
                "nicht aufdringlich",
                "dezent",
                "zurückhaltend",
                "zurueckhaltend",
                "büro",
                "buero",
                "office",
            )
        )

        if wants_discreet and projection is not None:
            if projection <= 7.3:
                preference_score += 3.0
            elif projection <= 7.8:
                preference_score += 1.0
            else:
                preference_score -= 2.0

        wants_office = any(term in query_text for term in ("büro", "buero", "office", "business"))

        if wants_office:
            if freshness is not None and freshness >= 6:
                preference_score += 1.5

            if sweetness is not None and sweetness <= 4:
                preference_score += 1.5

            if "powdery" in accords:
                preference_score += 1.5

            if "fresh" in accords:
                preference_score += 1.0

        normalized_preference_query = normalize_name_text(query_text)

        wants_summer = any(
            term in normalized_preference_query
            for term in (
                "sommer",
                "summer",
                "heiss",
                "hitze",
                "warmes wetter",
            )
        )

        if wants_summer:
            if freshness is not None:
                preference_score += (freshness / 10.0) * 4.0
            if sweetness is not None:
                preference_score += ((10.0 - sweetness) / 10.0) * 2.0
                if sweetness >= 8:
                    preference_score -= 1.5

            summer_accords = sum(
                accord in accords
                for accord in (
                    "fresh",
                    "citrus",
                    "aquatic",
                    "green",
                )
            )
            preference_score += min(
                2.4,
                summer_accords * 0.8,
            )

            if "gourmand" in accords:
                preference_score -= 1.0

        wants_winter = any(
            term in normalized_preference_query
            for term in (
                "winter",
                "kalte tage",
                "kaltes wetter",
                "cold weather",
            )
        )

        if wants_winter:
            warm_values = [
                value
                for value in (
                    sweetness,
                    woodiness,
                    spiciness,
                )
                if value is not None
            ]
            if warm_values:
                warmth = sum(warm_values) / len(warm_values)
                preference_score += (warmth / 10.0) * 4.0

            winter_accords = sum(
                accord in accords
                for accord in (
                    "sweet",
                    "spicy",
                    "gourmand",
                    "oriental",
                    "woody",
                    "creamy",
                )
            )
            preference_score += min(
                2.4,
                winter_accords * 0.6,
            )

        wants_spring = any(
            term in normalized_preference_query
            for term in (
                "fruhling",
                "spring",
            )
        )

        if wants_spring:
            if freshness is not None:
                preference_score += (freshness / 10.0) * 3.0

            if sweetness is not None:
                sweetness_distance = abs(sweetness - 4.5)
                preference_score += max(
                    0.0,
                    1.5 - sweetness_distance * 0.25,
                )

            spring_accords = sum(
                accord in accords
                for accord in (
                    "floral",
                    "fruity",
                    "green",
                    "citrus",
                    "fresh",
                )
            )
            preference_score += min(
                2.5,
                spring_accords * 0.65,
            )

        wants_autumn = any(
            term in normalized_preference_query
            for term in (
                "herbst",
                "autumn",
                "fall",
            )
        )

        if wants_autumn:
            warm_values = [
                value
                for value in (
                    sweetness,
                    woodiness,
                    spiciness,
                )
                if value is not None
            ]
            if warm_values:
                warmth = sum(warm_values) / len(warm_values)
                preference_score += (warmth / 10.0) * 3.5

            autumn_accords = sum(
                accord in accords
                for accord in (
                    "woody",
                    "spicy",
                    "sweet",
                    "fruity",
                    "smoky",
                    "oriental",
                )
            )
            preference_score += min(
                2.4,
                autumn_accords * 0.6,
            )

        wants_date = any(
            term in normalized_preference_query
            for term in (
                "date",
                "date night",
                "abend",
                "evening",
                "romantisch",
            )
        )

        if wants_date:
            warmth_values = [
                value
                for value in (
                    sweetness,
                    woodiness,
                    spiciness,
                )
                if value is not None
            ]
            if warmth_values:
                preference_score += (max(warmth_values) / 10.0) * 2.0

            if projection is not None:
                if 6.8 <= projection <= 8.3:
                    preference_score += 1.5
                elif projection > 8.8:
                    preference_score -= 0.5

        wants_party = any(
            term in normalized_preference_query
            for term in (
                "party",
                "club",
                "feiern",
                "nightlife",
            )
        )

        wants_everyday = any(
            term in normalized_preference_query
            for term in (
                "alltag",
                "taglich",
                "daily",
                "everyday",
            )
        )

        if wants_everyday:
            if freshness is not None:
                preference_score += 2.0 if 5 <= freshness <= 9 else 0.5
            if sweetness is not None:
                preference_score += 1.5 if sweetness <= 7 else -1.0
            if projection is not None:
                if 6.0 <= projection <= 7.8:
                    preference_score += 1.5
                elif projection > 8.5:
                    preference_score -= 0.75

        # Performance preference: longevity and projection.
        longevity = numeric_attribute("longevity")
        projection = numeric_attribute("projection")

        if wants_winter and longevity is not None:
            preference_score += (longevity / 10.0) * 2.0

        if wants_autumn and longevity is not None:
            preference_score += (longevity / 10.0) * 1.5

        if wants_date and longevity is not None:
            preference_score += (longevity / 10.0) * 2.0

        if wants_party:
            if projection is not None:
                preference_score += (projection / 10.0) * 3.0
            if longevity is not None:
                preference_score += (longevity / 10.0) * 2.5
            party_energy = max(
                value
                for value in (
                    sweetness,
                    spiciness,
                    0.0,
                )
                if value is not None
            )
            preference_score += (party_energy / 10.0) * 1.0

        if wants_everyday and longevity is not None and longevity >= 7.0:
            preference_score += min(
                1.5,
                (longevity - 6.5) * 0.75,
            )

        wants_longevity = any(
            term in query_text
            for term in (
                "haltbarkeit",
                "lange haltbarkeit",
                "long lasting",
                "long-lasting",
                "longevity",
                "lasting",
            )
        )

        if wants_longevity and longevity is not None:
            preference_score += (longevity / 10.0) * 4.0

        wants_projection = any(
            term in query_text
            for term in (
                "ausstrahlung",
                "projection",
                "sillage",
                "auffällig",
                "auffaellig",
                "noticeable",
                "strong projection",
            )
        )

        if wants_projection and projection is not None:
            preference_score += (projection / 10.0) * 4.0

        return base_score + preference_score

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

        products = [self._with_commerce_price(product) for product in self.products.values()]

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
                char for char in normalized if not unicodedata.combining(char)
            ).replace("ß", "ss")

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
        asks_for_alternative = any(marker in query_lower for marker in alternative_markers)

        # Conservative direct-name lookup for short, name-like requests.
        # This runs before generic recommendation logic so a typo such as
        # "Para L homme" resolves to Prada L'Homme instead of being interpreted
        # merely as a request for a men's fragrance.
        generic_query_words = {
            "ich",
            "suche",
            "such",
            "zeige",
            "zeig",
            "mir",
            "bitte",
            "einen",
            "eine",
            "ein",
            "duft",
            "parfum",
            "fragrance",
            "für",
            "fuer",
            "damen",
            "herren",
            "frauen",
            "männer",
            "maenner",
            "men",
            "women",
        }
        direct_query_words = [
            word for word in normalized_query.split() if word not in generic_query_words
        ]

        if not asks_for_alternative and 1 <= len(direct_query_words) <= 5:
            direct_matches = []

            for candidate in products:
                if not candidate.product_id.startswith("SC-"):
                    continue

                attrs = candidate.attributes or {}
                canonical_name = str(attrs.get("canonical_name") or "").strip()
                brand = str(candidate.brand or "").strip()

                name_variants = (
                    normalize_search_text(canonical_name),
                    normalize_search_text(f"{brand} {canonical_name}".strip()),
                )

                best_ratio = 0.0
                for variant in name_variants:
                    variant_words = [
                        word
                        for word in variant.split()
                        if word not in {"eau", "de", "parfum", "toilette", "extrait"}
                    ]
                    if not variant_words:
                        continue

                    token_scores = [
                        max(
                            SequenceMatcher(None, candidate_word, query_word).ratio()
                            for query_word in direct_query_words
                        )
                        for candidate_word in variant_words
                    ]
                    strong = [score for score in token_scores if score >= 0.80]
                    coverage = len(strong) / len(variant_words)

                    if len(variant_words) == 1:
                        ratio = strong[0] if strong else 0.0
                    elif coverage >= 0.67:
                        ratio = sum(strong) / len(strong)
                    else:
                        ratio = 0.0

                    best_ratio = max(best_ratio, ratio)

                if best_ratio >= 0.86:
                    direct_matches.append((best_ratio, candidate))

            direct_matches.sort(key=lambda item: item[0], reverse=True)

            if direct_matches:
                best_ratio, best_product = direct_matches[0]
                second_ratio = direct_matches[1][0] if len(direct_matches) > 1 else 0.0

                if best_ratio >= 0.90 and best_ratio - second_ratio >= 0.04:
                    if filters is not None and (
                        not within_price_and_rating(
                            best_product,
                            filters,
                        )
                        or not self._soft_filter(
                            best_product,
                            filters,
                        )
                    ):
                        return []

                    return [
                        self._customer_facing_product(
                            summary_of(best_product),
                            query_text=query,
                        )
                    ]

        if asks_for_alternative:
            benchmark_matches = []

            for candidate in products:
                attributes = candidate.attributes or {}

                if attributes.get("relationship_role") != "benchmark":
                    continue

                canonical_name = str(attributes.get("canonical_name") or "").strip()

                cluster_id = attributes.get("cluster_id")

                normalized_name = normalize_search_text(canonical_name)

                normalized_brand = normalize_search_text(candidate.brand or "")

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
                    token for token in normalized_name.split() if token not in ignored_name_tokens
                ]

                brand_tokens = [
                    token
                    for token in normalized_brand.split()
                    if token
                    not in {
                        "parfums",
                        "perfumes",
                        "de",
                    }
                ]

                matched_name_tokens = [token for token in name_tokens if token in query_tokens]

                exact_name_match = normalized_name and normalized_name in normalized_query

                brand_match = any(token in query_tokens for token in brand_tokens)

                if (
                    canonical_name
                    and cluster_id
                    and matched_name_tokens
                    and (exact_name_match or brand_match or len(name_tokens) == 1)
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
                    (product for product in products if product.product_id == target_anchor_id),
                    None,
                )

                reference_name = ""
                reference_accords = ""

                if target_anchor is not None:
                    anchor_attributes = target_anchor.attributes or {}
                    reference_accords = str(anchor_attributes.get("main_accords") or "").strip()
                    anchor_name = str(
                        anchor_attributes.get("canonical_name") or target_anchor.title
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
                        (product.attributes or {}).get("cluster_id") == target_cluster
                        and product.product_id != target_anchor_id
                    )
                ]

                explicitly_linked_products = [
                    product
                    for product in same_cluster_products
                    if self._relationship_to_anchor(
                        product,
                        target_anchor_id,
                    )
                    is not None
                ]

                if explicitly_linked_products:
                    same_cluster_products = explicitly_linked_products

                ranked_cluster = rank_products(
                    same_cluster_products,
                    query,
                    filters,
                    limit,
                    score=lambda product, tokens: self._alternative_score(
                        product,
                        tokens,
                        query,
                        target_anchor_id,
                    ),
                    hard_filter=within_price_and_rating,
                    soft_filter=self._soft_filter,
                )

                if ranked_cluster:
                    return [
                        self._customer_facing_product(
                            summary_of(product),
                            reference_name=reference_name,
                            reference_accords=reference_accords,
                            query_text=query,
                        )
                        for product in ranked_cluster
                    ]

        # Normal storefront search fallback.
        #
        # The demo catalog still contains legacy ACME fixtures alongside SCENTAI.
        # When the query clearly describes fragrance characteristics, keep discovery
        # inside the SCENTAI fragrance catalog instead of allowing unrelated demo
        # products to enter the shortlist.
        fragrance_query_markers = (
            "duft",
            "parfum",
            "fragrance",
            "sommerduft",
            "winterduft",
            "date duft",
            "büro duft",
            "buero duft",
            "frisch",
            "fresh",
            "zitrisch",
            "citrus",
            "süß",
            "suess",
            "sweet",
            "holzig",
            "woody",
            "würzig",
            "wuerzig",
            "spicy",
            "gourmand",
            "pudrig",
            "powdery",
            "aquatisch",
            "aquatic",
            "haltbarkeit",
            "longevity",
            "ausstrahlung",
            "projection",
            "sillage",
            "sommer",
            "summer",
            "winter",
            "frühling",
            "fruhling",
            "spring",
            "herbst",
            "autumn",
            "fall",
            "abend",
            "evening",
            "date",
            "party",
            "club",
            "feiern",
            "alltag",
            "daily",
            "everyday",
            "business",
            "office",
            "büro",
            "buero",
        )

        if any(marker in normalized_query for marker in fragrance_query_markers):
            products = [product for product in products if product.product_id.startswith("SC-")]

        ranked = rank_products(
            products,
            query,
            filters,
            limit,
            score=lambda product, tokens: self._score(product, tokens, query),
            hard_filter=within_price_and_rating,
            soft_filter=self._soft_filter,
        )

        return [
            self._customer_facing_product(
                summary_of(product),
                query_text=query,
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

    @staticmethod
    def _with_store_currency(cart: Cart) -> Cart:
        return cart.model_copy(update={"currency": "EUR"})

    async def get_cart(self, session: ShoppingSessionContext) -> Cart:
        return self._with_store_currency(self._carts.cart(session.session_id))

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
        cart_product = self._with_commerce_price(product)
        return self._with_store_currency(
            self._carts.put(session.session_id, cart_product, quantity)
        )

    async def update_cart_item(
        self, session: ShoppingSessionContext, product_id: str, quantity: int
    ) -> Cart:
        return self._with_store_currency(
            self._carts.set_quantity(session.session_id, product_id, quantity)
        )

    async def remove_from_cart(self, session: ShoppingSessionContext, product_id: str) -> Cart:
        return self._with_store_currency(self._carts.remove(session.session_id, product_id))

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
