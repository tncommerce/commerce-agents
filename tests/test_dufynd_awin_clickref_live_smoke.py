from __future__ import annotations

import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse

API = "https://scentai-api-kxhe.onrender.com"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def test_live_perfumetrader_clickout_propagates_content_id_to_awin_clickref() -> None:
    opener = urllib.request.build_opener(NoRedirect)
    url = (
        f"{API}/api/merchant-partners/perfumetrader/clickout"
        "?src=instagram"
        "&cmp=naxos_genesis_pilot"
        "&content=genesis_naxos_01"
        "&sid=awin-clickref-live-smoke"
    )

    try:
        opener.open(url, timeout=20)
    except urllib.error.HTTPError as exc:
        assert exc.code == 302
        location = exc.headers.get("Location") or ""
    else:
        raise AssertionError("Expected DUFYND partner clickout to return HTTP 302")

    parsed = urlparse(location)
    query = parse_qs(parsed.query)

    assert parsed.hostname in {"awin1.com", "www.awin1.com"}
    assert query["awinmid"] == ["11672"]
    assert query["awinaffid"] == ["3099222"]
    assert query["clickref"] == ["genesis_naxos_01"]
