"""One-shot public DUFYND HTTP contract inspection; never follows affiliate clickouts.

Run on GitHub public standard runner after API deployed and before frontend.
Source files/URLs are baked in from exact PR836 head a0ca39f (2026-10-26).
No credentials, purchases, postings, DB reads/writes or paid provider calls.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

API = "https://scentai-api-kxhe.onrender.com"
WEB = "https://dufynd.de"
AWIN = "https://www.awin1.com/pclick.php"
TOP = {
    "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100": ("924719", "38332629354", 91.95, 100),
    "SC-RABANNE-1-MILLION-EDT-100": ("707368", "37127263142", 102.95, 100),
    "SC-ARMANI-SWY-INTENSELY-100": ("849484", "37127260028", 107.95, 100),
    "SC-PDM-LAYTON-125": ("812773", "37127262708", 290.0, 125),
    "SC-VALENTINO-BORN-IN-ROMA-INTENSE-100": ("897029", "37127264452", 129.95, 100),
    "SC-PDM-ALTHAIR-125": ("904707", "37127265511", 290.0, 125),
    "SC-MONTBLANC-EXPLORER-100": ("849457", "37127262224", 113.0, 100),
    "SC-CREED-AVENTUS-100": ("827407", "37127260323", 354.0, 100),
    "SC-PRADA-LHOMME-100": ("815682", "43999996888", 117.95, 100),
    "SC-XERJOFF-NAXOS-100": ("836129", "46356123604", 242.0, 100),
}
PRODUCT_RABANNE = "SC-RABANNE-1-MILLION-EDT-100"
PERFUMETRADER = "perfumetrader-rabanne-1-million-edt-100"


class FailRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError(f"unexpected_redirect_{code}")


def read_https(url: str) -> tuple[int, bytes]:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in {
        "scentai-api-kxhe.onrender.com", "dufynd.de"
    } or parts.username or parts.password or parts.fragment:
        raise ValueError("unrecognized_smoke_host")
    request = Request(url, headers={
        "User-Agent": "DUFYND-production-readonly-qa/1.0",
        "Accept": "application/json, text/html",
    })
    opener = build_opener(FailRedirect())
    with opener.open(request, timeout=16) as response:
        if response.status != 200:
            raise ValueError(f"unexpected_status_{response.status}")
        raw = response.read(3_000_001)
        if len(raw) > 3_000_000:
            raise ValueError("response_oversize")
        return response.status, raw


def fetch_json(path: str) -> dict:
    # No clickout path is ever constructed or requested.
    if not path.startswith("/api/merchant-offers/SC-"):
        raise ValueError("only_public_offer_api_is_allowed")
    last = None
    for _ in range(3):
        try:
            _, raw = read_https(API + path)
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("invalid_json_object")
            return payload
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            last = type(exc).__name__
            time.sleep(1)
    raise ValueError("public_api_unavailable_" + str(last))


def exact_awin_link(link: str, aw_product_id: str) -> bool:
    parts = urlsplit(link)
    if (parts.scheme, parts.netloc, parts.path) != (
        "https", "www.awin1.com", "/pclick.php"
    ) or parts.fragment:
        return False
    params = parse_qs(parts.query, strict_parsing=True)
    return params == {"p": [aw_product_id], "a": ["3099222"], "m": ["31081"]}


def assert_top_ten() -> dict:
    successes = []
    for pid, (sku, awid, total, ml) in TOP.items():
        payload = fetch_json("/api/merchant-offers/" + pid)
        if payload.get("product_id") != pid or not isinstance(payload.get("offers"), list):
            raise ValueError("unexpected_public_offer_schema_" + pid)
        chosen = [x for x in payload["offers"] if x.get("merchant_id") == "top-parfuemerie"]
        if len(chosen) != 1:
            raise ValueError(f"missing_or_duplicate_top_offer_for_{pid}")
        offer = chosen[0]
        if (offer.get("merchant_product_id") != sku
                or offer.get("in_stock") is not True
                or not isinstance(offer.get("total_price"), (float, int))
                or abs(float(offer["total_price"]) - total) > 0.01
                or not isinstance(offer.get("variant_label"), str)
                or f"{ml} ml" not in offer["variant_label"]
                or offer.get("clickout_path") != "/api/clickout/" + offer["offer_id"]
                or not exact_awin_link(str(offer.get("affiliate_link") or ""), awid)
        ):
            raise ValueError("wrong_variant_price_or_link_" + pid)
        try:
            checked = datetime.fromisoformat(offer["last_updated_at"].replace("Z", "+00:00"))
            age = datetime.now(UTC) - checked.astimezone(UTC)
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("invalid_price_timestamp_" + pid) from exc
        if not timedelta(minutes=-5) <= age <= timedelta(hours=72):
            raise ValueError("expired_or_future_price_" + pid)
        if pid == PRODUCT_RABANNE:
            cheaper = next((x for x in payload["offers"]
                            if x.get("offer_id") == PERFUMETRADER), None)
            if not cheaper or cheaper.get("merchant_id") != "perfumetrader":
                raise ValueError("missing_qualified_perfumetrader_rabanne")
            if cheaper.get("total_price", 100000) >= offer["total_price"]:
                raise ValueError("perfumetrader_not_cheaper")
            if payload.get("best_offer_id") != PERFUMETRADER:
                raise ValueError("best_offer_rabanne_no_longer_price_leading")
        successes.append({"product_id": pid, "sku": sku, "price_age_hours": round(age.total_seconds()/3600, 1)})
    return {"api_top_offers_validated": len(successes), "offers": successes, "rabanne_cheaper_perfumetrader_preserved": True}


def assert_web() -> dict:
    paths = ["/", "/duft", "/duft/rabanne-1-million"]
    checks = []
    for path in paths:
        _, raw = read_https(WEB + path)
        html = raw.decode("utf-8", errors="replace").lower()
        if "dufynd" not in html:
            raise ValueError("website_identity_missing_for_" + path)
        if path.startswith("/duft") and ("rabanne" not in html and "/duft" not in html):
            raise ValueError("website_fragrance_content_missing_for_" + path)
        checks.append(path)
    return {"website_routes_200": checks}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=["api", "full"])
    args = parser.parse_args()
    try:
        result = {"status": "READ_ONLY_LIVE_API_VERIFIED",
                  "phase": args.phase, **assert_top_ten()}
        if args.phase == "full":
            result.update(assert_web())
            result["status"] = "READ_ONLY_COUPLED_RELEASE_VERIFIED"
    except Exception as exc:
        print("DUFYND_RELEASE_QA_BLOCKER=" +
              json.dumps({"phase": args.phase, "type": type(exc).__name__,
                          "description": str(exc)[:280]}))
        return 2
    print("DUFYND_RELEASE_QA_SUCCESS=" + json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
