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

    check = next(check for check in report.checks if check.name == "merchant_offers_notino_eclaire")
    assert report.ok is True
    assert check.ok is True
    assert check.status_code == 404
    assert "publication-gated" in check.detail


def test_deployment_smoke_accepts_only_safe_empty_rabanne_offer_with_explicit_warning() -> None:
    """A merchant-side outage must not turn a healthy deployment into a failed deploy."""
    empty = {
        "product_id": CRITICAL_PRODUCT_ID,
        "best_offer_id": None,
        "offers": [],
        "affiliate_disclosure": "Affiliate disclosure",
    }
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        expected_indexing="disabled",
        allow_safe_rabanne_absence=True,
        transport=transport(offers_payload=empty),
    )
    assert report.ok is True
    assert len(report.checks) == 18
    check = next(
        check for check in report.checks if check.name == "merchant_offers_rabanne_1_million"
    )
    assert check.ok is True
    assert "BUSINESS_WARNING" in check.detail
    assert "NOT confirmed" in check.detail
    assert check.status_code == 200


@pytest.mark.parametrize(
    "malformed",
    [
        {
            "product_id": CRITICAL_PRODUCT_ID,
            "best_offer_id": "stale-offer",
            "offers": [],
            "affiliate_disclosure": "Disclosure",
        },
        {
            "product_id": "SC-WRONG",
            "best_offer_id": None,
            "offers": [],
            "affiliate_disclosure": "Disclosure",
        },
        {
            "product_id": CRITICAL_PRODUCT_ID,
            "best_offer_id": None,
            "offers": [],
            "affiliate_disclosure": "",
        },
        {
            "product_id": CRITICAL_PRODUCT_ID,
            "best_offer_id": None,
            "offers": ["malformed"],
            "affiliate_disclosure": "Disclosure",
        },
    ],
)
def test_deployment_smoke_still_rejects_malformed_or_unsafe_offers(malformed: dict) -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        allow_safe_rabanne_absence=True,
        transport=transport(offers_payload=malformed),
    )
    assert report.ok is False
    assert any(c.name == "merchant_offers_rabanne_1_million" and not c.ok for c in report.checks)


def test_deployment_smoke_does_not_waive_indexing_or_route_regressions() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        expected_indexing="enabled",
        allow_safe_rabanne_absence=True,
        transport=transport(
            robots_text="User-agent: *\\nDisallow: /\\n",
            offers_payload={
                "product_id": CRITICAL_PRODUCT_ID,
                "best_offer_id": None,
                "offers": [],
                "affiliate_disclosure": "Disclosure",
            },
        ),
    )
    assert report.ok is False
    assert any(c.name == "robots_policy" and not c.ok for c in report.checks)


# Regression: deployment-only absence must never masquerade as a confirmed offer.
def _safe_empty_offer(product_id: str = CRITICAL_PRODUCT_ID) -> dict:
    return {
        "product_id": product_id,
        "offers": [],
        "best_offer_id": None,
        "affiliate_disclosure": "Affiliate disclosure",
    }


@pytest.mark.parametrize("body", [None, [], [1], True, 1, "invalid"])
@pytest.mark.parametrize("allow_absence", [False, True])
def test_non_object_offer_json_returns_failed_check_not_exception(body, allow_absence) -> None:
    import json

    original = transport()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/api/merchant-offers/{CRITICAL_PRODUCT_ID}":
            return httpx.Response(
                200, content=json.dumps(body), headers={"content-type": "application/json"}
            )
        return original.handle_request(request)

    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        allow_safe_rabanne_absence=allow_absence,
        transport=httpx.MockTransport(handler),
    )
    assert report.ok is False
    assert len(report.checks) == 18
    check = next(c for c in report.checks if c.name == "merchant_offers_rabanne_1_million")
    assert check.ok is False
    assert "JSON object" in check.detail


def test_safe_empty_contract_requires_explicit_null_best_offer_id() -> None:
    empty = _safe_empty_offer()
    del empty["best_offer_id"]
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        allow_safe_rabanne_absence=True,
        transport=transport(offers_payload=empty),
    )
    assert report.ok is False


@pytest.mark.parametrize(
    "product_id, requirements",
    [
        (NOTINO_ECLAIRE_PRODUCT_ID, {}),
        ("SC-OTHER", {}),
        (CRITICAL_PRODUCT_ID, {"expected_offer_id": "required-offer"}),
        (CRITICAL_PRODUCT_ID, {"expected_merchant_id": "required-merchant"}),
        (CRITICAL_PRODUCT_ID, {"require_affiliate_link": True}),
    ],
)
def test_absence_cannot_waive_another_product_or_required_affiliate(
    product_id, requirements
) -> None:
    from scripts.dufynd_production_smoke import _check_merchant_offers

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == f"/api/merchant-offers/{product_id}"
        return httpx.Response(200, json=_safe_empty_offer(product_id))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        check = _check_merchant_offers(
            client,
            "https://api.dufynd.test",
            product_id,
            allow_safe_absence=True,
            **requirements,
        )
    assert check.ok is False


@pytest.mark.parametrize("status", [201, 202, 206, 302, 404, 500, 503])
def test_empty_warning_requires_completed_http_200_contract(status) -> None:
    original = transport()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/api/merchant-offers/{CRITICAL_PRODUCT_ID}":
            return httpx.Response(status, json=_safe_empty_offer())
        return original.handle_request(request)

    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        allow_safe_rabanne_absence=True,
        transport=httpx.MockTransport(handler),
    )
    assert report.ok is False


@pytest.mark.parametrize("path", ["/start", CRITICAL_PRODUCT_PATH, "/duftfinder", "/vergleich"])
def test_safe_absence_never_waives_a_broken_customer_route(path) -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        allow_safe_rabanne_absence=True,
        transport=transport(offers_payload=_safe_empty_offer(), broken_storefront_path=path),
    )
    assert report.ok is False
    assert any(not c.ok and c.status_code == 404 for c in report.checks)


def test_safe_absence_does_not_waive_real_noindex_policy() -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        expected_indexing="enabled",
        allow_safe_rabanne_absence=True,
        transport=transport(
            offers_payload=_safe_empty_offer(), robots_text="User-agent: *\nDisallow: /\n"
        ),
    )
    assert report.ok is False
    check = next(c for c in report.checks if c.name == "robots_policy")
    assert "reports indexing disabled" in check.detail


@pytest.mark.parametrize("broken", [False, True])
def test_deployment_report_counts_absence_as_warning_not_pass(broken) -> None:
    report = run_smoke(
        storefront_url="https://dufynd.de",
        api_url="https://api.dufynd.test",
        allow_safe_rabanne_absence=True,
        transport=transport(
            offers_payload=_safe_empty_offer(),
            broken_storefront_path="/vergleich" if broken else None,
        ),
    )
    payload = report.to_dict()
    assert payload["ok"] is (not broken)
    assert payload["status"] == ("failed" if broken else "degraded")
    assert payload["passed_checks"] == (16 if broken else 17)
    assert payload["warning_checks"] == 1
    assert payload["failed_checks"] == int(broken)
    assert len(payload["checks"]) == 18
    check = next(c for c in payload["checks"] if c["name"] == "merchant_offers_rabanne_1_million")
    assert check["warning_code"] == "no_eligible_rabanne_offer"
    assert "NOT confirmed" in check["detail"]


def test_normal_and_strict_failure_reports_have_no_warning() -> None:
    for empty in (False, True):
        report = run_smoke(
            storefront_url="https://dufynd.de",
            api_url="https://api.dufynd.test",
            transport=transport(offers_payload=_safe_empty_offer() if empty else None),
        )
        payload = report.to_dict()
        assert payload["status"] == ("failed" if empty else "passed")
        assert payload["passed_checks"] == (17 if empty else 18)
        assert payload["failed_checks"] == int(empty)
        assert payload["warning_checks"] == 0


@pytest.mark.parametrize("machine_readable", [False, True])
@pytest.mark.parametrize("allow_absence", [False, True])
def test_cli_keeps_strict_default_and_exposes_degradation(
    monkeypatch, capsys, machine_readable, allow_absence
) -> None:
    import json
    import sys

    from scripts import dufynd_production_smoke as smoke

    real_run = smoke.run_smoke
    calls = []

    def isolated_run(**kwargs):
        calls.append(kwargs)
        return real_run(**kwargs, transport=transport(offers_payload=_safe_empty_offer()))

    monkeypatch.setattr(smoke, "run_smoke", isolated_run)
    args = ["dufynd_production_smoke.py", "--api-url", "https://api.dufynd.test"]
    if machine_readable:
        args.append("--machine-readable")
    if allow_absence:
        args.append("--allow-safe-rabanne-absence")
    monkeypatch.setattr(sys, "argv", args)
    assert smoke.main() == (0 if allow_absence else 20)
    assert len(calls) == 1
    assert calls[0]["allow_safe_rabanne_absence"] is allow_absence
    stdout = capsys.readouterr().out
    if machine_readable:
        data = json.loads(stdout)
        assert data["status"] == ("degraded" if allow_absence else "failed")
        assert data["warning_checks"] == int(allow_absence)
    else:
        assert "checks=18/18" not in stdout
        assert "status=" + ("degraded" if allow_absence else "failed") in stdout
        assert "warnings=" + str(int(allow_absence)) in stdout
        if allow_absence:
            assert "WARN merchant_offers_rabanne_1_million" in stdout
            assert "NOT confirmed" in stdout
