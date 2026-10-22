"""Verified-offer evidence I/O must not stall unrelated async buyer requests."""

from __future__ import annotations

import asyncio
from pathlib import Path
from threading import Event

import pytest

from examples.retail.api import main as retail_api


def test_both_offer_routes_use_existing_worker_pool() -> None:
    source = Path("examples/retail/api/main.py").read_text(encoding="utf-8")
    assert "from starlette.concurrency import run_in_threadpool" in source
    assert "await run_in_threadpool(offer_store.offers_for, product_id)" in source
    assert "await run_in_threadpool(offer_store.eligible_offer, offer_id)" in source
    assert "    offers = offer_store.offers_for(product_id)" not in source
    assert "    offer = offer_store.eligible_offer(offer_id)" not in source
    assert "offer_clickout_target(offer)" in source
    assert "if offer is None or not _live_dufynd_offer_product" in source


@pytest.mark.asyncio
async def test_slow_cached_evidence_does_not_block_other_async_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = Event()
    release = Event()
    product = "SC-RABANNE-1-MILLION-EDT-100"

    def delayed_verified_offers(product_id: str) -> list:
        assert product_id == product
        started.set()
        release.wait(timeout=1.0)
        return []

    # No network, external clicks, measurement events or merchant offers.
    monkeypatch.setattr(retail_api, "_live_dufynd_offer_product", lambda _: True)
    monkeypatch.setattr(retail_api.offer_store, "offers_for", delayed_verified_offers)
    pending = asyncio.create_task(retail_api.product_offers(product))
    try:
        await asyncio.wait_for(asyncio.to_thread(started.wait, 0.5), timeout=0.7)
        assert started.is_set()
        assert not pending.done(), "the ASGI event loop waited on synchronous offer I/O"
        marker = asyncio.Event()
        asyncio.get_running_loop().call_soon(marker.set)
        await asyncio.wait_for(marker.wait(), timeout=0.2)
    finally:
        release.set()

    result = await asyncio.wait_for(pending, timeout=1.0)
    assert result["product_id"] == product
    assert result["best_offer_id"] is None
    assert result["offers"] == []
