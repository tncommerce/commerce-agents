from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from retail.api import main


@pytest.fixture
def blocked_client(monkeypatch):
    monkeypatch.setattr(main.offer_store, "eligible_offer", lambda _: None)

    def forbidden(*args, **kwargs):
        raise AssertionError("Rejected offers must not create tracking events")

    monkeypatch.setattr(main.clickout_tracker, "record", forbidden)
    monkeypatch.setattr(main.analytics_tracker, "record", forbidden)
    return TestClient(main.app, base_url="http://localhost")


def test_browser_gets_safe_recovery_without_clickout(blocked_client):
    import re
    from html import unescape

    response = blocked_client.get(
        "/api/clickout/expired?src=instagram&cmp=launch&content=post1&sid=stable-session&qa=1",
        headers={"Accept": "text/html,application/xhtml+xml"},
    )
    assert response.status_code == 404
    assert "Dieses Angebot ist gerade nicht verfügbar" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert "location" not in response.headers
    links = re.findall(r'href="([^"]+)"', response.text)
    assert len(links) == 2
    for link in links:
        target = urlsplit(unescape(link))
        assert target.scheme == "https" and target.netloc == "dufynd.de"
        assert target.path in {"/duft", "/vergleich"}
        assert parse_qs(target.query) == {
            "src": ["instagram"],
            "cmp": ["launch"],
            "content": ["post1"],
            "sid": ["stable-session"],
            "qa": ["1"],
        }


def test_unsafe_input_is_not_reflected(blocked_client):
    response = blocked_client.get(
        "/api/clickout/missing",
        params={"src": "<script>alert(1)</script>", "next": "https://evil.test", "qa": "false"},
        headers={"Accept": "text/html"},
    )
    assert "<script>" not in response.text and "evil.test" not in response.text
    assert "qa=" not in response.text


def test_json_clients_keep_existing_contract(blocked_client):
    response = blocked_client.get("/api/clickout/missing", headers={"Accept": "application/json"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Offer not available"}
    response = blocked_client.get("/api/merchant-offers/missing", headers={"Accept": "text/html"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Product not available"}


def test_unsafe_target_gets_same_recovery(blocked_client, monkeypatch):
    monkeypatch.setattr(
        main.offer_store, "eligible_offer", lambda _: SimpleNamespace(product_id="SC-LIVE")
    )
    monkeypatch.setattr(main, "_live_dufynd_offer_product", lambda _: True)
    monkeypatch.setattr(main, "offer_clickout_target", lambda _: None)
    response = blocked_client.get("/api/clickout/unsafe", headers={"Accept": "text/html"})
    assert response.status_code == 404 and "Zum Duftkatalog" in response.text
