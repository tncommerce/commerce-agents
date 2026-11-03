"""Exercise real ASGI catalog routes while synchronous offer evidence is stalled."""

from __future__ import annotations

import asyncio
from threading import Event

import httpx
import pytest
from examples.retail.api import main as retail_api

PRODUCT_ID = "SC-RABANNE-1-MILLION-EDT-100"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/products?category=fragrance&limit=1",
        f"/api/products/{PRODUCT_ID}",
        f"/api/merchant-offers/{PRODUCT_ID}",
    ],
)
async def test_slow_offer_read_cannot_stall_real_health_request(monkeypatch, path):
    started, release = Event(), Event()
    timed_out = Event()

    def delayed_offers(_product_id):
        # Hold the first actual evidence read, not a mocked scope predicate.
        if not started.is_set():
            started.set()
            if not release.wait(timeout=2):
                timed_out.set()
        return []

    monkeypatch.setattr(retail_api.offer_store, "offers_for", delayed_offers)
    transport = httpx.ASGITransport(app=retail_api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        pending = asyncio.create_task(client.get(path))
        try:
            assert await asyncio.wait_for(asyncio.to_thread(started.wait, 1), timeout=3)
            # The delayed catalog read must still be waiting, while liveness
            # can independently respond. No merchant/network request is made.
            health = await asyncio.wait_for(client.get("/api/health"), timeout=1)
            assert health.status_code == 200
            assert health.json()["ok"] is True
            assert not timed_out.is_set(), "synchronous catalog evidence blocked the event loop"
            assert not pending.done(), "health could run only after the stalled read finished"
        finally:
            release.set()
            response = await asyncio.wait_for(pending, timeout=2)
        assert response.status_code == 200
        body = response.json()
        if path.startswith("/api/products?"):
            assert len(body["products"]) == 1
            assert body["products"][0]["category"] == "fragrance"
        elif path.startswith("/api/products/"):
            assert body["product_id"] == PRODUCT_ID
            assert body["attributes"]["price_source"] == "market_reference"
        else:
            assert body["product_id"] == PRODUCT_ID
            assert body["offers"] == []
            assert body["best_offer_id"] is None


def test_product_scope_guard_is_local_and_preserves_visibility_and_stock(monkeypatch):
    def forbidden_read(_product_id):
        raise AssertionError("scope validation must not perform merchant evidence I/O")

    monkeypatch.setattr(retail_api.offer_store, "offers_for", forbidden_read)
    assert retail_api._live_dufynd_offer_product(PRODUCT_ID) is True
    assert retail_api._live_dufynd_offer_product("unknown") is False
    fixture_id = next(pid for pid in retail_api.backend.products if not pid.startswith("SC-"))
    assert retail_api._live_dufynd_offer_product(fixture_id) is False
    blocked = set(retail_api.backend._blocked_dufynd_product_ids)
    monkeypatch.setattr(retail_api.backend, "_blocked_dufynd_product_ids", blocked | {PRODUCT_ID})
    assert retail_api._live_dufynd_offer_product(PRODUCT_ID) is False
    monkeypatch.setattr(retail_api.backend, "_blocked_dufynd_product_ids", blocked)
    product = retail_api.backend.products[PRODUCT_ID]
    monkeypatch.setitem(
        retail_api.backend.products, PRODUCT_ID, product.model_copy(update={"in_stock": False})
    )
    assert retail_api._live_dufynd_offer_product(PRODUCT_ID) is False


@pytest.mark.asyncio
async def test_catalog_visibility_and_unknown_product_errors_are_preserved(monkeypatch):
    monkeypatch.setattr(retail_api.offer_store, "offers_for", lambda _: [])
    monkeypatch.setattr(
        retail_api.backend,
        "_blocked_dufynd_product_ids",
        set(retail_api.backend._blocked_dufynd_product_ids) | {PRODUCT_ID},
    )
    transport = httpx.ASGITransport(app=retail_api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        listing = await client.get("/api/products?category=fragrance&limit=100")
        assert listing.status_code == 200
        assert PRODUCT_ID not in {row["product_id"] for row in listing.json()["products"]}
        for path in (
            f"/api/products/{PRODUCT_ID}",
            "/api/products/missing",
            f"/api/merchant-offers/{PRODUCT_ID}",
        ):
            assert (await client.get(path)).status_code == 404
