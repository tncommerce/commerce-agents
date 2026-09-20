from __future__ import annotations

import httpx
import pytest
from scripts.dufynd_production_smoke import run_smoke


def transport(*, health_payload=None, partners_payload=None) -> httpx.MockTransport:
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
            return httpx.Response(200, text="<html>DUFYND</html>")

        if request.url.path == "/api/health":
            return httpx.Response(200, json=resolved_health)

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
        "api_health",
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
