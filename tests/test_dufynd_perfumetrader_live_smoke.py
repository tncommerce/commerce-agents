from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

API = "https://scentai-api-kxhe.onrender.com"
STOREFRONT = "https://dufynd.de/"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get_json_with_retry(url: str, attempts: int = 18, delay: int = 10) -> dict:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
            time.sleep(delay)
    assert last_error is not None
    raise last_error


def test_perfumetrader_partner_is_live() -> None:
    payload = _get_json_with_retry(f"{API}/api/merchant-partners")
    partners = payload.get("partners", [])
    perfumetrader = next(
        (row for row in partners if row.get("merchant_id") == "perfumetrader"),
        None,
    )

    assert perfumetrader is not None
    assert perfumetrader.get("merchant_name") == "Perfumetrader"


def test_live_dufynd_partner_clickout_targets_verified_awin_link() -> None:
    opener = urllib.request.build_opener(NoRedirect)
    url = (
        f"{API}/api/merchant-partners/perfumetrader/clickout"
        "?src=organic"
        "&cmp=perfumetrader_live_smoke"
        "&content=partner_activation_001"
        "&sid=perfumetrader-live-smoke-ci"
    )

    try:
        opener.open(url, timeout=20)
    except urllib.error.HTTPError as exc:
        assert exc.code == 302
        location = exc.headers.get("Location") or ""
    else:
        raise AssertionError("Expected DUFYND partner clickout to return HTTP 302")

    assert "awin1.com/cread.php" in location
    assert "awinmid=11672" in location
    assert "awinaffid=3099222" in location


def test_dufynd_storefront_is_live() -> None:
    with urllib.request.urlopen(STOREFRONT, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")

    assert response.status == 200
    assert "DUFYND" in body
