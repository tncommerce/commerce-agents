# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""ACME retail example API: the mock retailer behind the shared storefront routes, the
merchant router under /api/merchant, and the retail-only routes below.

    uvicorn retail.api.main:app --app-dir examples --reload --port 8000

Memory here is file-backed (``data/.memory-store.json``, gitignored) and seeded once per
user, so what a shopper asks the store to remember, or to forget, survives a restart.
"""

from __future__ import annotations

from fastapi import BackgroundTasks, HTTPException
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
from .analytics import (
    AnalyticsEventRequest,
    FirstPartyAnalyticsTracker,
)
from .clickout_recovery import clickout_exception_handler
from .jarvis_owner_auth import create_control_room_router
from .merchant import create_merchant_router
from .merchant_offers import (
    MerchantClickoutTracker,
    MerchantOfferStore,
    customer_offer_payload,
    offer_clickout_target,
)
from .merchant_partners import (
    MerchantPartnerStore,
    customer_partner_payload,
)
from .mock_retail import DATA_DIR, MockRetail

load_demo_env(DATA_DIR.parent)
PRODUCT_IMAGES = DATA_DIR.parent / "storefront-web" / "public" / "products"

offer_store = MerchantOfferStore(DATA_DIR / "merchant_offers.json")
partner_store = MerchantPartnerStore(DATA_DIR / "merchant_partners.json")
clickout_tracker = MerchantClickoutTracker(DATA_DIR / ".merchant_clickouts.jsonl")
analytics_tracker = FirstPartyAnalyticsTracker(DATA_DIR / ".analytics_events.jsonl")
backend = MockRetail(offer_store=offer_store)


def _live_dufynd_offer_product(product_id: str) -> bool:
    product = backend.customer_product(product_id)
    return bool(
        product is not None
        and product.product_id.startswith("SC-")
        and product.category == "fragrance"
        and product.in_stock
    )


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
    title="DUFYND API",
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
app.add_exception_handler(HTTPException, clickout_exception_handler)
app.include_router(create_merchant_router(backend, InMemoryMemoryStore()), prefix="/api/merchant")
app.include_router(create_control_room_router())
# The merchant portal shows the storefront's listing photos, so the API serves them to both apps.
app.mount("/products", StaticFiles(directory=PRODUCT_IMAGES, check_dir=False), name="products")


@app.get("/api/merchant-partners")
async def merchant_partners() -> dict:
    partners = partner_store.active()

    return {
        "partners": [customer_partner_payload(partner) for partner in partners],
        "affiliate_disclosure": (
            "Bei Käufen über Partnerlinks kann DUFYND eine Provision erhalten. "
            "Die Händlerauswahl beeinflusst nicht die Duftempfehlung."
        ),
    }


@app.get("/api/merchant-partners/{partner_key}/clickout")
async def merchant_partner_clickout(
    partner_key: str,
    background_tasks: BackgroundTasks,
    src: str | None = None,
    cmp: str | None = None,
    content: str | None = None,
    sid: str | None = None,
    qa: bool = False,
    measurement: str | None = None,
) -> RedirectResponse:
    partner = partner_store.eligible(partner_key)
    if partner is None or partner.affiliate_url is None:
        raise HTTPException(
            status_code=404,
            detail="Merchant partner not available",
        )

    # Redirect URLs are copyable/replayable and cannot prove that a browser's
    # optional measurement choice is still current. Keep navigation functional
    # but never create DUFYND analytics or dynamic click references from this GET.
    return RedirectResponse(
        url=partner.affiliate_url,
        status_code=302,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )

@app.get("/api/merchant-offers/{product_id}")
async def product_offers(product_id: str) -> dict:
    if not _live_dufynd_offer_product(product_id):
        raise HTTPException(status_code=404, detail="Product not available")

    offers = offer_store.offers_for(product_id)

    return {
        "product_id": product_id,
        "best_offer_id": offers[0].offer_id if offers else None,
        "offers": [customer_offer_payload(offer) for offer in offers],
        "affiliate_disclosure": (
            "Bei Käufen über Partnerlinks kann DUFYND eine Provision erhalten. "
            "Für dich ändert sich der Preis dadurch nicht."
        ),
    }


@app.post("/api/analytics/events")
async def analytics_event(
    request: AnalyticsEventRequest,
    record: host.CurrentSession,
    measurement: str | None = None,
) -> dict:
    # A missing, invalid, denied or QA-only signal never permits telemetry.
    if measurement != "granted-v1":
        return {"ok": True, "recorded": False, "storage": "disabled"}

    # Scope the client retry key to its stable funnel identity. A renewed API
    # transport session must not turn a lost response into a second event.
    from uuid import NAMESPACE_URL, uuid5

    session_id = request.analytics_session_id or record.session_id
    event_id, storage = await analytics_tracker.record(
        session_id=session_id,
        event_id=(
            str(uuid5(NAMESPACE_URL, f"dufynd-analytics:{session_id}:{request.event_id}"))
            if request.event_id
            else None
        ),
        event=request.event,
        internal_qa=request.internal_qa,
        product_id=request.product_id,
        offer_id=request.offer_id,
        source=request.source,
        acquisition_source=request.acquisition_source,
        campaign_id=request.campaign_id,
        content_id=request.content_id,
        search_term=request.search_term,
        result_count=request.result_count,
        surface=request.surface,
        related_product_id=request.related_product_id,
        item_position=request.item_position,
    )
    return {"ok": True, "event_id": event_id, "storage": storage}


@app.get("/api/clickout/{offer_id}")
async def merchant_clickout(
    offer_id: str,
    background_tasks: BackgroundTasks,
    src: str | None = None,
    cmp: str | None = None,
    content: str | None = None,
    sid: str | None = None,
    qa: bool = False,
    measurement: str | None = None,
) -> RedirectResponse:
    offer = offer_store.eligible_offer(offer_id)
    if offer is None or not _live_dufynd_offer_product(offer.product_id):
        raise HTTPException(status_code=404, detail="Offer not available")

    target = offer_clickout_target(offer)
    if target is None:
        raise HTTPException(status_code=404, detail="Offer not available")

    # A copied GET cannot demonstrate current optional consent. The affiliate
    # destination remains available, while DUFYND measurement is emitted by the
    # live browser click handler through the consent-gated analytics POST.
    return RedirectResponse(
        url=target,
        status_code=302,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )

@app.post("/api/cart/add")
async def cart_add(request: CartAddRequest, record: host.CurrentSession) -> dict:
    if str(request.product_id).startswith("SC-"):
        raise HTTPException(
            status_code=409,
            detail=(
                "DUFYND fragrance purchases use verified merchant offers, "
                "not the internal demo cart."
            ),
        )

    return await host.direct_add(
        record,
        request,
        note="Customer tapped the add-to-cart button on {title} ({product_id}), quantity {quantity}.",
    )
