from __future__ import annotations

import httpx
import pytest
from scripts.dufynd_production_smoke import run_smoke

SAMPLE_PRODUCT_ID = "SC-TEST-FRAGRANCE-EDP-100"


def transport(
    *,
    health_payload=None,
    partners_payload=None,
    broken_storefront_path: str | None = None,
    detail_product_id: str = SAMPLE_PRODUCT_ID,
) -> httpx.MockTransport:
    resolved_health = health_payload or {
        "ok": True,
        "store": "DUFYND",
        "products": 119,
        "skills": ["search-discovery"],
        "model": "claude-sonnet-5",
    }
    resolved_partners = partners_payload or {
        "partners": [],
        "affiliate_disclosure": "Affiliate disclosure",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "dufynd.de":
            if broken_storefront_path and request.url.path == broken_storefront_path:
                return httpx.Response(404, text="Not found")
            return httpx.Response(200, text="<html>DUFYND</html>")

        if request.url.path == "/api/health":
            return httpx.Response(200, json=resolved_health)

        if request.url.path == "/api/products":
            return httpx.Response(
                200,
                json={
                    "products": [
                        {
                            "product_id": SAMPLE_PRODUCT_ID,
                            "brand": "Test Brand",
                            "name": "Test Fragrance",
                        }
                    ]
                },
            )

        if request.url.path == f"/api/products/{SAMPLE_PRODUCT_ID}":
            return httpx.Response(
                200,
                json={
                    "product_id": detail_product_id,
                    "brand": "Test Brand",
                    "name": "Test Fragrance",
                },
            )

        if request.url.path == "/api/merchant-partners":
            return httpx.Response(200, json=resolved_partners)

        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_smoke_passes_for_expected_contract() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        transport=transport(),
    )

    assert report.ok is True
    assert [check.name for check in report.checks] == [
        "storefront",
        "storefront_duftfinder",
        "storefront_vergleich",
        "storefront_alternatives",
        "storefront_impressum",
        "storefront_datenschutz",
        "storefront_transparenz",
        "api_health",
        "product_catalog",
        "product_detail",
        "merchant_partners",
    ]


def test_smoke_fails_on_wrong_api_identity() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        transport=transport(
            health_payload={
                "ok": True,
                "store": "SCENTAI",
                "products": 119,
                "skills": ["search-discovery"],
                "model": "claude-sonnet-5",
            }
        ),
    )

    assert report.ok is False
    assert next(check for check in report.checks if check.name == "api_health").ok is False


def test_smoke_rejects_non_absolute_url() -> None:
    with pytest.raises(ValueError, match="absolute"):
        run_smoke(
            storefront_url="dufynd.de",
            api_url="https://api.dufynd.test",
            transport=transport(),
        )


def test_smoke_fails_when_storefront_is_not_dufynd() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "dufynd.de":
            return httpx.Response(200, text="<html>Wrong brand</html>")
        if request.url.path == "/api/health":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "store": "DUFYND",
                    "products": 119,
                    "skills": ["search-discovery"],
                    "model": "claude-sonnet-5",
                },
            )
        if request.url.path == "/api/products":
            return httpx.Response(
                200,
                json={"products": [{"product_id": SAMPLE_PRODUCT_ID}]},
            )
        if request.url.path == f"/api/products/{SAMPLE_PRODUCT_ID}":
            return httpx.Response(200, json={"product_id": SAMPLE_PRODUCT_ID})
        if request.url.path == "/api/merchant-partners":
            return httpx.Response(
                200,
                json={
                    "partners": [],
                    "affiliate_disclosure": "Affiliate disclosure",
                },
            )
        return httpx.Response(404)

    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        transport=httpx.MockTransport(handler),
    )

    assert report.ok is False
    assert report.checks[0].name == "storefront"
    assert report.checks[0].ok is False


def test_smoke_fails_when_critical_storefront_route_is_missing() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        transport=transport(broken_storefront_path="/vergleich"),
    )

    check = next(check for check in report.checks if check.name == "storefront_vergleich")
    assert report.ok is False
    assert check.ok is False
    assert check.status_code == 404


def test_smoke_fails_on_product_detail_identity_mismatch() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        transport=transport(detail_product_id="SC-WRONG-ID"),
    )

    check = next(check for check in report.checks if check.name == "product_detail")
    assert report.ok is False
    assert check.ok is False
