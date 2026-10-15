"""Actual DUFYND ASGI routes and middleware; synthetic stores, no outgoing traffic.

The session dependency is overridden deliberately, not the routes or consent gate.
This proves HTTP parsing and background-task dispatch, not a signed consent receipt.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from fastapi.routing import APIRoute

from retail.api import main
from retail.api.merchant_offers import MerchantOffer, offer_clickout_target
from retail.api.merchant_partners import MerchantPartner

GRANT = "granted-v1"
PID = "SC-CONSENT-HOST-QA"
OFFER = "qa-consent-offer"
PARTNER = "qa-consent-partner"
SID = "qa-measurement-host-123456789"
CLICK_ID = "00000000-0000-4000-8000-000000000026"
PATHS = [f"/api/clickout/{OFFER}", f"/api/merchant-partners/{PARTNER}/clickout"]


@pytest.fixture
def consent_host(monkeypatch):
    rows, clicks = [], []
    offer = MerchantOffer(
        offer_id=OFFER,
        product_id=PID,
        merchant_id=PARTNER,
        merchant_name="QA merchant",
        price=99,
        shipping_cost=0,
        in_stock=True,
        product_url="https://merchant.example.test/fixture",
        affiliate_url="https://www.awin1.com/cread.php?awinmid=0&awinaffid=0",
        last_updated_at=datetime.now(UTC),
    )
    partner = MerchantPartner(
        merchant_id=PARTNER,
        merchant_name="QA merchant",
        status="active",
        affiliate_url="https://www.awin1.com/cread.php?awinmid=0&awinaffid=0",
        last_verified_at=datetime.now(UTC),
    )
    available = {"offer": True, "partner": True, "product": True}

    async def record(**kwargs):
        rows.append(kwargs)
        return kwargs.get("event_id") or CLICK_ID, "test-memory"

    def click_record(actual_offer, **kwargs):
        assert actual_offer.offer_id == OFFER
        clicks.append(kwargs)
        return CLICK_ID

    async def forbid_async(*args, **kwargs):
        raise AssertionError("An ASGI consent test attempted an external HTTP request")

    def forbid_sync(*args, **kwargs):
        raise AssertionError("An ASGI consent test attempted an external HTTP request")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbid_async)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbid_sync)
    monkeypatch.setattr(main, "analytics_tracker", SimpleNamespace(record=record))
    monkeypatch.setattr(main, "clickout_tracker", SimpleNamespace(record=click_record))
    monkeypatch.setattr(
        main,
        "offer_store",
        SimpleNamespace(
            eligible_offer=lambda key: offer if key == OFFER and available["offer"] else None
        ),
    )
    monkeypatch.setattr(
        main,
        "partner_store",
        SimpleNamespace(
            eligible=lambda key: partner if key == PARTNER and available["partner"] else None
        ),
    )
    monkeypatch.setattr(
        main, "_live_dufynd_offer_product", lambda pid: pid == PID and available["product"]
    )
    # Included routers and static mounts are not API endpoints and need not have
    # a .path or .dependant. Select only the actual directly registered endpoint.
    routes = [
        route
        for route in main.app.routes
        if isinstance(route, APIRoute) and route.path == "/api/analytics/events"
    ]
    assert len(routes) == 1
    assert routes[0].endpoint is main.analytics_event
    dependencies = [item.call for item in routes[0].dependant.dependencies if item.name == "record"]
    assert len(dependencies) == 1
    dependency = dependencies[0]
    old_overrides = main.app.dependency_overrides.copy()
    main.app.dependency_overrides[dependency] = lambda: SimpleNamespace(
        session_id="qa-functional-advisor-123456789"
    )
    try:
        yield SimpleNamespace(
            app=main.app,
            rows=rows,
            clicks=clicks,
            offer=offer,
            partner=partner,
            available=available,
        )
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(old_overrides)


def request(host, method, path, **kwargs):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=host.app),
            base_url="http://127.0.0.1",
            follow_redirects=False,
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(run())


def context(measurement=None):
    params = {"sid": SID, "src": "instagram", "cmp": "qa_cmp", "content": "qa_content", "qa": "1"}
    if measurement is not None:
        params["measurement"] = measurement
    return params


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("measurement", [None, "", "denied", "granted", "GRANTED-V1", "granted-v2"])
def test_http_redirect_without_permission_never_records(consent_host, path, measurement):
    response = request(consent_host, "GET", path, params=context(measurement))
    assert response.status_code == 302
    expected = (
        offer_clickout_target(consent_host.offer)
        if path == PATHS[0]
        else consent_host.partner.affiliate_url
    )
    assert response.headers["location"] == expected
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert consent_host.rows == []
    assert consent_host.clicks == []
    assert "set-cookie" not in response.headers
    assert not response.history


@pytest.mark.parametrize("path", PATHS)
def test_http_copied_granted_redirect_is_never_measurement_evidence(consent_host, path):
    response = request(consent_host, "GET", path, params=context(GRANT))
    assert response.status_code == 302
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    expected = (
        offer_clickout_target(consent_host.offer)
        if path == PATHS[0]
        else consent_host.partner.affiliate_url
    )
    assert response.headers["location"] == expected
    assert consent_host.rows == []
    assert consent_host.clicks == []
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("measurement", [None, "", "denied", "granted", "GRANTED-V1", "granted-v2"])
def test_http_event_without_permission_never_records(consent_host, measurement):
    response = request(
        consent_host,
        "POST",
        "/api/analytics/events",
        params={} if measurement is None else {"measurement": measurement},
        json={
            "event": "page_view",
            "internal_qa": True,
            "analytics_session_id": SID,
            "measurement": GRANT,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "recorded": False, "storage": "disabled"}
    assert consent_host.rows == []
    assert consent_host.clicks == []


def test_http_grant_then_ungranted_request_keeps_gate(consent_host):
    payload = {"event": "page_view", "internal_qa": True, "analytics_session_id": SID}
    granted = request(
        consent_host, "POST", "/api/analytics/events", params={"measurement": GRANT}, json=payload
    )
    assert granted.status_code == 200
    assert granted.json()["storage"] == "test-memory"
    assert len(consent_host.rows) == 1
    denied = request(consent_host, "POST", "/api/analytics/events", json=payload)
    assert denied.status_code == 200
    assert denied.json()["recorded"] is False
    assert len(consent_host.rows) == 1
    # Redirect GETs are independently fail-closed, so a copied granted URL cannot replay measurement.
    replay = request(consent_host, "GET", PATHS[0], params=context(GRANT))
    assert replay.status_code == 302
    assert len(consent_host.rows) == 1
    assert consent_host.clicks == []


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("measurement", [None, GRANT])
def test_unavailable_targets_remain_unavailable(consent_host, path, measurement):
    consent_host.available.update(offer=False, partner=False)
    response = request(consent_host, "GET", path, params=context(measurement))
    assert response.status_code == 404
    assert "location" not in response.headers
    assert consent_host.rows == []
    assert consent_host.clicks == []


def test_product_visibility_is_not_bypassed_by_measurement(consent_host):
    consent_host.available["product"] = False
    response = request(consent_host, "GET", PATHS[0], params=context(GRANT))
    assert response.status_code == 404
    assert consent_host.rows == []
    assert consent_host.clicks == []


def test_http_validation_still_rejects_bad_event(consent_host):
    response = request(
        consent_host,
        "POST",
        "/api/analytics/events",
        params={"measurement": GRANT},
        json={"event": "not-an-analytics-event", "event_id": "bad-uuid"},
    )
    assert response.status_code == 422
    assert consent_host.rows == []


def test_real_cors_preflight_for_measurement_request(consent_host):
    response = request(
        consent_host,
        "OPTIONS",
        "/api/analytics/events?measurement=granted-v1",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-session-id",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
    assert consent_host.rows == []
    assert consent_host.clicks == []
