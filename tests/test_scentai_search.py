# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest

from examples.retail.api.mock_retail import MockRetail
from shopping_agent import ProductDetails, ShoppingSessionContext


@pytest.mark.asyncio
async def test_scentai_named_fragrance_search_tolerates_small_typos() -> None:
    backend = MockRetail()
    session = ShoppingSessionContext(session_id="typo-test", user_id=None)

    results = await backend.search_products(
        session,
        "Para L homme",
        limit=4,
    )

    assert results
    assert results[0].product_id == "SC-PRADA-LHOMME-100"


@pytest.mark.asyncio
async def test_scentai_named_fragrance_search_tolerates_missing_letter() -> None:
    backend = MockRetail()
    session = ShoppingSessionContext(session_id="typo-test-2", user_id=None)

    results = await backend.search_products(
        session,
        "Bois Imperal",
        limit=4,
    )

    assert results
    assert results[0].product_id == "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100"


def _sc_product(
    product_id: str,
    *,
    target_group: str,
    audience_lean: str | None = None,
) -> ProductDetails:
    attributes = {
        "canonical_name": product_id,
        "target_group": target_group,
        "main_accords": "floral, fresh",
        "freshness": "6",
        "sweetness": "5",
        "woodiness": "3",
        "spiciness": "2",
        "longevity": "7",
        "projection": "7",
    }
    if audience_lean is not None:
        attributes["audience_lean"] = audience_lean

    return ProductDetails(
        product_id=f"SC-{product_id}",
        title=product_id,
        brand="Test",
        price=50.0,
        category="fragrance",
        attributes=attributes,
        in_stock=True,
    )


def test_scentai_womens_request_prefers_womens_product() -> None:
    backend = MockRetail()
    women = _sc_product("Women", target_group="women")
    men = _sc_product("Men", target_group="men")

    women_score = backend._score(women, ["damenduft"], "Ich suche einen Damenduft")
    men_score = backend._score(men, ["damenduft"], "Ich suche einen Damenduft")

    assert women_score > men_score


def test_scentai_feminine_unisex_request_uses_audience_lean() -> None:
    backend = MockRetail()
    feminine = _sc_product(
        "FeminineUnisex",
        target_group="unisex",
        audience_lean="feminine",
    )
    masculine = _sc_product(
        "MasculineUnisex",
        target_group="unisex",
        audience_lean="masculine",
    )

    feminine_score = backend._score(
        feminine,
        ["feminin", "unisex"],
        "Ich suche einen femininen Unisex Duft",
    )
    masculine_score = backend._score(
        masculine,
        ["feminin", "unisex"],
        "Ich suche einen femininen Unisex Duft",
    )

    assert feminine_score > masculine_score
