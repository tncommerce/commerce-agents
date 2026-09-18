# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""Phase 2C reality / regression tests for SCENTAI.

These tests cover edge cases that are easy for a recommendation system to
mishandle:
- overlapping fragrance names must resolve to the right reference;
- a hard budget must never cause a named-reference search to drift into an
  unrelated fragrance cluster;
- low-budget named-reference searches may legitimately return no result;
- broad fragrance discovery must stay inside the SCENTAI fragrance catalog.
"""

from shopping_agent import SearchFilters


async def test_absolu_aventus_resolves_to_absolu_cluster_not_regular_aventus(
    backend,
    session,
):
    hits = await backend.search_products(
        session,
        "Alternative zu Creed Absolu Aventus",
        SearchFilters(max_price=60),
        limit=5,
    )

    ids = [product.product_id for product in hits]

    assert ids[:2] == [
        "SC-AFNAN-SUPREMACY-COLLECTORS-100",
        "SC-MAISON-ASRAR-VANGUARD-100",
    ]
    assert "SC-ARMAF-CDNIM-EDP-200" not in ids
    assert "SC-MONTBLANC-EXPLORER-100" not in ids


async def test_naxos_impossible_budget_does_not_broaden_to_unrelated_products(
    backend,
    session,
):
    hits = await backend.search_products(
        session,
        "Alternative zu Xerjoff Naxos",
        SearchFilters(max_price=20),
        limit=5,
    )

    assert hits == []


async def test_dior_homme_intense_impossible_budget_returns_no_unrelated_fallback(
    backend,
    session,
):
    hits = await backend.search_products(
        session,
        "Alternative zu Dior Homme Intense",
        SearchFilters(max_price=15),
        limit=5,
    )

    assert hits == []


async def test_naxos_under_30_keeps_only_explicitly_linked_budget_options(
    backend,
    session,
):
    hits = await backend.search_products(
        session,
        "Alternative zu Xerjoff Naxos",
        SearchFilters(max_price=30),
        limit=5,
    )

    ids = [product.product_id for product in hits]

    assert ids == [
        "SC-NUSUK-ATEEQ-100",
        "SC-RAYHAAN-ITALIA-100",
    ]
    assert all(product.price <= 30 for product in hits)


async def test_general_fragrance_discovery_returns_only_scentai_products(
    backend,
    session,
):
    hits = await backend.search_products(
        session,
        "frisch zitrisch nicht zu süß",
        SearchFilters(max_price=100),
        limit=8,
    )

    assert hits
    assert all(product.product_id.startswith("SC-") for product in hits)


async def test_strong_performance_under_100_respects_request_and_budget(
    backend,
    session,
):
    hits = await backend.search_products(
        session,
        "sehr starke Haltbarkeit und Ausstrahlung",
        SearchFilters(max_price=100),
        limit=5,
    )

    assert hits
    assert all(product.price <= 100 for product in hits)

    top = [backend.product(product.product_id) for product in hits[:3]]
    assert all(product is not None for product in top)

    for product in top:
        longevity = float(product.attributes["longevity"])
        projection = float(product.attributes["projection"])
        assert (longevity + projection) / 2 >= 7.8
