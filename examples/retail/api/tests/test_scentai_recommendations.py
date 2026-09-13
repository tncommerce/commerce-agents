# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""SCENTAI recommendation-engine acceptance tests.

These tests define the first Phase 2 ranking contract:
- explicit budgets are hard constraints;
- named-reference searches stay inside the relevant fragrance cluster;
- relationship quality and community evidence should beat a tiny rating edge;
- explicit scent-profile and performance preferences should materially affect ranking.
"""

from shopping_agent import SearchFilters


async def test_imagination_alternatives_respect_budget_and_rank_evidence(backend, session):
    hits = await backend.search_products(
        session,
        "Alternative zu Louis Vuitton Imagination",
        SearchFilters(max_price=60),
        limit=5,
    )

    ids = [product.product_id for product in hits]

    assert ids
    assert "SC-LV-IMAGINATION-100" not in ids
    assert all(product.price <= 60 for product in hits)

    # General default recommendation:
    # Marwa EDP has far more community evidence than the Extrait while keeping
    # a high-confidence relationship to Imagination. Hectic is the stronger
    # performance-oriented second option.
    assert ids[:3] == [
        "SC-ARABIYAT-MARWA-EDP-100",
        "SC-BUJAIRAMI-HECTIC-100",
        "SC-ARABIYAT-MARWA-EXTRAIT-60",
    ]


async def test_layton_alternative_under_40_is_detour_noir(backend, session):
    hits = await backend.search_products(
        session,
        "Alternative zu Parfums de Marly Layton",
        SearchFilters(max_price=40),
        limit=5,
    )

    assert hits
    assert hits[0].product_id == "SC-AL-HARAMAIN-DETOUR-NOIR-100"
    assert all(product.price <= 40 for product in hits)


async def test_tygar_style_under_50_prefers_turathi_blue(backend, session):
    hits = await backend.search_products(
        session,
        "Ähnlich zu Bvlgari Tygar",
        SearchFilters(max_price=50),
        limit=5,
    )

    ids = [product.product_id for product in hits]

    assert ids
    assert all(product.price <= 50 for product in hits)
    assert ids[0] == "SC-AFNAN-TURATHI-BLUE-90"
    assert "SC-MAISON-ASRAR-REGENT-100" in ids[:2]


async def test_fresh_not_too_sweet_search_prioritizes_matching_profiles(backend, session):
    hits = await backend.search_products(
        session,
        "frischer Sommerduft, nicht zu süß",
        SearchFilters(max_price=60),
        limit=5,
    )

    assert hits
    assert all(product.price <= 60 for product in hits)

    top = [backend.product(product.product_id) for product in hits[:3]]
    assert all(product is not None for product in top)

    for product in top:
        freshness = float(product.attributes["freshness"])
        sweetness = float(product.attributes["sweetness"])
        assert freshness >= 8
        assert sweetness <= 6


async def test_performance_search_prioritizes_longevity_and_projection(backend, session):
    hits = await backend.search_products(
        session,
        "starke Haltbarkeit und Ausstrahlung",
        limit=5,
    )

    assert hits

    top = [backend.product(product.product_id) for product in hits[:3]]
    assert all(product is not None for product in top)

    for product in top:
        longevity = float(product.attributes["longevity"])
        projection = float(product.attributes["projection"])
        assert (longevity + projection) / 2 >= 7.8
