from __future__ import annotations

import httpx
import pytest
from scripts.dufynd_production_smoke import (
    CRITICAL_PRODUCT_ID,
    NOTINO_ECLAIRE_OFFER_ID,
    NOTINO_ECLAIRE_PRODUCT_ID,
    run_smoke,
)

SAMPLE_PRODUCT_ID = "SC-TEST-FRAGRANCE-EDP-100"
CRITICAL_PRODUCT_PATH = "/duft/rabanne-1-million"


def transport(
    *,
    health_payload=None,
    partners_payload=None,
    offers_payload=None,
    eclaire_offers_payload=None,
    eclaire_public: bool = True,
    broken_storefront_path: str | None = None,
    detail_product_id: str = SAMPLE_PRODUCT_ID,
    robots_text: str = "User-agent: *\nDisallow: /\n",
    sitemap_text: str = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://dufynd.de</loc></url></urlset>"
    ),
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
    resolved_offers = (
        offers_payload
        if offers_payload is not None
        else {
            "product_id": CRITICAL_PRODUCT_ID,
            "best_offer_id": "perfumetrader-rabanne-1-million-edt-100",
            "offers": [
                {
                    "offer_id": "perfumetrader-rabanne-1-million-edt-100",
                    "product_id": CRITICAL_PRODUCT_ID,
                    "merchant_id": "perfumetrader",
                    "merchant_name": "Perfumetrader",
                    "price": 89.0,
                    "currency": "EUR",
                    "total_price": 89.0,
                    "in_stock": True,
                    "clickout_path": ("/api/clickout/perfumetrader-rabanne-1-million-edt-100"),
                    "affiliate_link": True,
                    "last_updated_at": "2026-09-30T12:04:36+00:00",
                }
            ],
            "affiliate_disclosure": "Affiliate disclosure",
        }
    )
    resolved_eclaire_offers = (
        eclaire_offers_payload
        if eclaire_offers_payload is not None
        else {
            "product_id": NOTINO_ECLAIRE_PRODUCT_ID,
            "best_offer_id": NOTINO_ECLAIRE_OFFER_ID,
            "offers": [
                {
                    "offer_id": NOTINO_ECLAIRE_OFFER_ID,
                    "product_id": NOTINO_ECLAIRE_PRODUCT_ID,
                    "merchant_id": "notino",
                    "merchant_name": "Notino",
                    "price": 33.5,
                    "currency": "EUR",
                    "total_price": 33.5,
                    "in_stock": True,
                    "clickout_path": f"/api/clickout/{NOTINO_ECLAIRE_OFFER_ID}",
                    "affiliate_link": True,
                    "last_updated_at": "2026-09-30T16:22:00+00:00",
                }
            ],
            "affiliate_disclosure": "Affiliate disclosure",
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "dufynd.de":
            if broken_storefront_path and request.url.path == broken_storefront_path:
                return httpx.Response(404, text="Not found")
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text=robots_text)
            if request.url.path == "/sitemap.xml":
                return httpx.Response(200, text=sitemap_text)
            if request.url.path == CRITICAL_PRODUCT_PATH:
                return httpx.Response(
                    200,
                    text="<html>DUFYND Rabanne 1 Million</html>",
                )
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

        if request.url.path == f"/api/products/{CRITICAL_PRODUCT_ID}":
            return httpx.Response(
                200,
                json={
                    "product_id": CRITICAL_PRODUCT_ID,
                    "brand": "Rabanne",
                    "title": "Rabanne 1 Million Eau de Toilette 100 ml",
                },
            )

        if request.url.path == f"/api/products/{NOTINO_ECLAIRE_PRODUCT_ID}":
            if not eclaire_public:
                return httpx.Response(404, json={"detail": "not found"})
            return httpx.Response(
                200,
                json={
                    "product_id": NOTINO_ECLAIRE_PRODUCT_ID,
                    "brand": "Lattafa",
                    "title": "Lattafa Eclaire Eau de Parfum 100 ml",
                },
            )

        if request.url.path == f"/api/merchant-offers/{CRITICAL_PRODUCT_ID}":
            return httpx.Response(200, json=resolved_offers)

        if request.url.path == f"/api/merchant-offers/{NOTINO_ECLAIRE_PRODUCT_ID}":
            if not eclaire_public:
                return httpx.Response(404, json={"detail": "not found"})
            return httpx.Response(200, json=resolved_eclaire_offers)

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
        "storefront_social_start",
        "storefront_rabanne_1_million",
        "storefront_duftfinder",
        "storefront_vergleich",
        "storefront_alternatives",
        "storefront_impressum",
        "storefront_datenschutz",
        "storefront_transparenz",
        "robots_policy",
        "sitemap",
        "api_health",
        "product_catalog",
        "product_detail",
        "product_detail_rabanne_1_million",
        "merchant_offers_rabanne_1_million",
        "merchant_offers_notino_eclaire",
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
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
            if request.url.path == "/sitemap.xml":
                return httpx.Response(
                    200,
                    text=(
                        '<?xml version="1.0"?>'
                        "<urlset><url><loc>https://dufynd.de</loc></url></urlset>"
                    ),
                )
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


def test_smoke_accepts_valid_disabled_robots_policy_by_default() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        transport=transport(),
    )

    check = next(check for check in report.checks if check.name == "robots_policy")
    assert check.ok is True
    assert "disabled" in check.detail


def test_smoke_can_assert_enabled_indexing() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        expected_indexing="enabled",
        transport=transport(
            robots_text=("User-agent: *\nAllow: /\nSitemap: https://dufynd.de/sitemap.xml\n")
        ),
    )

    check = next(check for check in report.checks if check.name == "robots_policy")
    assert report.ok is True
    assert check.ok is True
    assert "enabled" in check.detail


def test_smoke_fails_when_indexing_expectation_mismatches() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        expected_indexing="enabled",
        transport=transport(),
    )

    check = next(check for check in report.checks if check.name == "robots_policy")
    assert report.ok is False
    assert check.ok is False
    assert "disabled" in check.detail


def test_smoke_fails_on_unrecognized_robots_policy() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        transport=transport(robots_text="User-agent: *\n"),
    )

    check = next(check for check in report.checks if check.name == "robots_policy")
    assert report.ok is False
    assert check.ok is False


def test_smoke_fails_when_sitemap_is_missing_canonical_site() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        transport=transport(
            sitemap_text=(
                '<?xml version="1.0"?><urlset><url><loc>https://wrong.example</loc></url></urlset>'
            )
        ),
    )

    check = next(check for check in report.checks if check.name == "sitemap")
    assert report.ok is False
    assert check.ok is False


def test_smoke_rejects_invalid_expected_indexing_value() -> None:
    with pytest.raises(ValueError, match="expected_indexing"):
        run_smoke(
            storefront_url="https://dufynd.de",
            api_url="https://api.dufynd.test",
            expected_indexing="later",
            transport=transport(),
        )


def test_smoke_fails_when_social_start_route_is_missing() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        transport=transport(broken_storefront_path="/start"),
    )

    check = next(check for check in report.checks if check.name == "storefront_social_start")
    assert report.ok is False
    assert check.ok is False
    assert check.status_code == 404


def test_smoke_fails_when_rabanne_1_million_route_is_missing() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        transport=transport(broken_storefront_path=CRITICAL_PRODUCT_PATH),
    )

    check = next(check for check in report.checks if check.name == "storefront_rabanne_1_million")
    assert report.ok is False
    assert check.ok is False
    assert check.status_code == 404


def test_smoke_fails_when_rabanne_1_million_api_detail_is_missing() -> None:
    base_transport = transport()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/api/products/{CRITICAL_PRODUCT_ID}":
            return httpx.Response(404, json={"detail": "not found"})
        return base_transport.handle_request(request)

    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        transport=httpx.MockTransport(handler),
    )

    check = next(
        check for check in report.checks if check.name == "product_detail_rabanne_1_million"
    )
    assert report.ok is False
    assert check.ok is False
    assert check.status_code == 404


def test_smoke_fails_when_critical_merchant_offers_are_missing() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        transport=transport(
            offers_payload={
                "product_id": CRITICAL_PRODUCT_ID,
                "best_offer_id": None,
                "offers": [],
                "affiliate_disclosure": "Affiliate disclosure",
            }
        ),
    )

    check = next(
        check for check in report.checks if check.name == "merchant_offers_rabanne_1_million"
    )
    assert report.ok is False
    assert check.ok is False
    assert "no current offer" in check.detail


def test_smoke_fails_on_unsafe_merchant_clickout_path() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        transport=transport(
            offers_payload={
                "product_id": CRITICAL_PRODUCT_ID,
                "best_offer_id": "unsafe-offer",
                "offers": [
                    {
                        "offer_id": "unsafe-offer",
                        "product_id": CRITICAL_PRODUCT_ID,
                        "merchant_id": "merchant-a",
                        "merchant_name": "Merchant A",
                        "price": 89.0,
                        "currency": "EUR",
                        "in_stock": True,
                        "clickout_path": "https://merchant.example/product",
                        "affiliate_link": False,
                    }
                ],
                "affiliate_disclosure": "Affiliate disclosure",
            }
        ),
    )

    check = next(
        check for check in report.checks if check.name == "merchant_offers_rabanne_1_million"
    )
    assert report.ok is False
    assert check.ok is False
    assert "stale or unsafe" in check.detail


def test_smoke_fails_when_notino_eclaire_is_not_affiliate_routed() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        transport=transport(
            eclaire_offers_payload={
                "product_id": NOTINO_ECLAIRE_PRODUCT_ID,
                "best_offer_id": NOTINO_ECLAIRE_OFFER_ID,
                "offers": [
                    {
                        "offer_id": NOTINO_ECLAIRE_OFFER_ID,
                        "product_id": NOTINO_ECLAIRE_PRODUCT_ID,
                        "merchant_id": "notino",
                        "merchant_name": "Notino",
                        "price": 33.5,
                        "currency": "EUR",
                        "total_price": 33.5,
                        "in_stock": True,
                        "clickout_path": f"/api/clickout/{NOTINO_ECLAIRE_OFFER_ID}",
                        "affiliate_link": False,
                        "last_updated_at": "2026-09-30T16:22:00+00:00",
                    }
                ],
                "affiliate_disclosure": "Affiliate disclosure",
            }
        ),
    )

    check = next(check for check in report.checks if check.name == "merchant_offers_notino_eclaire")
    assert report.ok is False
    assert check.ok is False
    assert "expected_offer_ok=False" in check.detail


def test_smoke_accepts_hidden_notino_eclaire_while_publication_gate_is_closed() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        transport=transport(eclaire_public=False),
    )

    check = next(
        check for check in report.checks if check.name == "merchant_offers_notino_eclaire"
    )
    assert report.ok is True
    assert check.ok is True
    assert check.status_code == 404
    assert "publication-gated" in check.detail
