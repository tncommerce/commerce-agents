# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""ACME retail example API: the mock retailer behind the shared storefront routes, the
merchant router under /api/merchant, and the retail-only routes below.

    uvicorn retail.api.main:app --app-dir examples --reload --port 8000

Memory here is file-backed (``data/.memory-store.json``, gitignored) and seeded once per
user, so what a shopper asks the store to remember, or to forget, survives a restart.
"""

from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from commerce_common.memory import InMemoryMemoryStore, JsonFileMemoryStore
from demo_common import (
    REPO_ROOT,
    CartAddRequest,
    MemorySeeder,
    build_storefront_host,
    load_demo_env,
)
from shopping_agent import ProductDetails
from shopping_agent_runtime import ShoppingAgent

from .agent_config import build_shopping_config
from .analytics import AnalyticsEventRequest, FirstPartyAnalyticsTracker
from .merchant import create_merchant_router
from .merchant_offers import MerchantClickoutTracker, MerchantOfferStore, customer_offer_payload
from .mock_retail import DATA_DIR, MockRetail

load_demo_env(DATA_DIR.parent)
PRODUCT_IMAGES = DATA_DIR.parent / "storefront-web" / "public" / "products"

offer_store = MerchantOfferStore(DATA_DIR / "merchant_offers.json")
clickout_tracker = MerchantClickoutTracker(DATA_DIR / ".merchant_clickouts.jsonl")
analytics_tracker = FirstPartyAnalyticsTracker(DATA_DIR / ".analytics_events.jsonl")
backend = MockRetail(offer_store=offer_store)
agent = ShoppingAgent(
    backend=backend,
    skills_dir=REPO_ROOT / "shopping-agent" / "skills",
    config=build_shopping_config(),
    memory_store=JsonFileMemoryStore(DATA_DIR / ".memory-store.json"),
)


def product_detail(product: ProductDetails) -> dict:
    # The original retail demo synthesizes price-history and review-aspect widgets.
    # Those are not real SCENTAI evidence, so never expose them for fragrance catalog items.
    if product.product_id.startswith("SC-"):
        return product.model_dump() | {
            "price_intelligence": None,
            "review_aspects": None,
        }

    return product.model_dump() | {
        "price_intelligence": backend.price_intelligence(product.product_id),
        "review_aspects": backend.review_aspects(product.product_id),
    }


host = build_storefront_host(
    title="SCENTAI API",
    example_root=DATA_DIR.parent,
    backend=backend,
    agent=agent,
    memory_seeder=MemorySeeder(
        DATA_DIR / "memory-seed.json", marker=DATA_DIR / ".memory-seeded.json"
    ),
    product_of=backend.customer_product,
    product_detail=product_detail,
)
app = host.app
app.include_router(create_merchant_router(backend, InMemoryMemoryStore()), prefix="/api/merchant")
# The merchant portal shows the storefront's listing photos, so the API serves them to both apps.
app.mount("/products", StaticFiles(directory=PRODUCT_IMAGES, check_dir=False), name="products")


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "service": "scentai-api",
    }


@app.get("/api/merchant-offers/{product_id}")
async def product_offers(product_id: str) -> dict:
    offers = offer_store.offers_for(product_id)

    return {
        "product_id": product_id,
        "best_offer_id": offers[0].offer_id if offers else None,
        "offers": [customer_offer_payload(offer) for offer in offers],
        "affiliate_disclosure": (
            "Bei Käufen über Partnerlinks kann SCENTAI eine Provision erhalten. "
            "Für dich ändert sich der Preis dadurch nicht."
        ),
    }


@app.post("/api/analytics/events")
async def analytics_event(
    request: AnalyticsEventRequest,
    record: host.CurrentSession,
) -> dict:
    event_id, storage = await analytics_tracker.record(
        session_id=request.analytics_session_id or record.session_id,
        event=request.event,
        product_id=request.product_id,
        source=request.source,
        search_term=request.search_term,
        result_count=request.result_count,
        surface=request.surface,
        related_product_id=request.related_product_id,
        item_position=request.item_position,
    )
    return {"ok": True, "event_id": event_id, "storage": storage}


@app.get("/api/clickout/{offer_id}")
async def merchant_clickout(offer_id: str) -> RedirectResponse:
    offer = offer_store.eligible_offer(offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not available")

    clickout_tracker.record(offer)
    target = offer.affiliate_url or offer.product_url
    return RedirectResponse(url=target, status_code=302)


@app.post("/api/cart/add")
async def cart_add(request: CartAddRequest, record: host.CurrentSession) -> dict:
    return await host.direct_add(
        record,
        request,
        note="Customer tapped the add-to-cart button on {title} ({product_id}), quantity {quantity}.",
    )
