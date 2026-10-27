"""Verify released DUFYND original-photo placement without clickouts or logins.

One-time production QA on public product HTML. This never opens affiliate URLs,
calls purchase actions, reads customer data, or changes any production state.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PROD_SHA = "36cc84c34791284e4245ab4504ae020434dca89e"
BASE = "https://dufynd.de"
ROWS = (
    ("SC-PDM-DELINA-EDP-75", "parfums-de-marly-delina", "825869_3700578501998_051.png"),
    ("SC-YSL-BLACK-OPIUM-EDP-90", "yves-saint-laurent-black-opium", "787670_3365440787971_051.png"),
    ("SC-YSL-LIBRE-EDP-90", "yves-saint-laurent-libre", "856448_3614272648425_051.png"),
    ("SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100", "essential-parfums-bois-imperial", "924719_3770010614630_051.png"),
    ("SC-ARMANI-SWY-INTENSELY-100", "giorgio-armani-stronger-with-you-intensely", "849484_3614272225718_051.png"),
    ("SC-PDM-LAYTON-125", "parfums-de-marly-layton", "812773_3700578502322_051.png"),
    ("SC-VALENTINO-BORN-IN-ROMA-INTENSE-100", "valentino-uomo-born-in-roma-intense", "897029_3614273790826_051.png"),
    ("SC-PDM-ALTHAIR-125", "parfums-de-marly-althair", "904707_904707_061.png"),
    ("SC-RABANNE-1-MILLION-EDT-100", "rabanne-1-million", "707368_3349666007921_051.png"),
    ("SC-LANCOME-LA-VIE-EST-BELLE-EDP-100", "lancome-la-vie-est-belle", "3605533286555.webp"),
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("unapproved_http_redirect")


class Assets(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.photos = []
        self.original_elements = []
        self.title = ""
        self.in_title = False
        self.canonicals = []
        self.meta_robots = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if "data-dufynd-original-photo" in d:
            self.original_elements.append(d)
        if tag == "img":
            self.photos.append(d)
        if tag == "title":
            self.in_title = True
        if tag == "link" and d.get("rel") == "canonical":
            self.canonicals.append(d.get("href", ""))
        if tag == "meta" and d.get("name") == "robots":
            self.meta_robots.append(d.get("content", ""))

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def self_test():
    assert len(ROWS) == len(set(row[0] for row in ROWS)) == 10
    assert len({row[1] for row in ROWS}) == 10
    assert all(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) for _, slug, _ in ROWS)
    assert all(re.fullmatch(r"[0-9]+(?:_[0-9]+){1,2}_[0-9]+\.(?:png|webp)", fn) or fn == "3605533286555.webp" for _, _, fn in ROWS)
    for _, slug, _ in ROWS:
        u = urlsplit(BASE + "/duft/" + slug)
        assert (u.scheme, u.netloc, u.path.startswith("/duft/")) == ("https", "dufynd.de", True)
    fixture = '<title>DUFYND · Test</title><img data-dufynd-original-photo="true" src="https://merchant.example/a.png">'
    obj = Assets()
    obj.feed(fixture)
    assert obj.title == "DUFYND · Test"
    assert len(obj.original_elements) == 1


def read_site(slug: str) -> Assets:
    url = BASE + "/duft/" + slug
    req = Request(
        url,
        headers={"User-Agent": "DUFYND-independent-read-only-photo-smoke/1.0", "Accept": "text/html"},
    )
    with build_opener(NoRedirect()).open(req, timeout=15) as response:
        if response.status != 200:
            raise ValueError("non_200_public_detail_" + slug)
        payload = response.read(2_500_001)
    if len(payload) > 2_500_000:
        raise ValueError("public_html_oversized_" + slug)
    html = payload.decode("utf-8", errors="replace")
    parser = Assets()
    parser.feed(html)
    if "dufynd" not in html.lower():
        raise ValueError("site_identity_missing_" + slug)
    return parser


def main():
    self_test()
    if "--self-test" in sys.argv:
        print("LIVE_PHOTO_QA_SELFTEST=OK")
        return 0
    results = []
    for pid, slug, file_name in ROWS:
        try:
            parsed = read_site(slug)
            found = [
                a for a in parsed.photos
                if file_name in a.get("src", "") and
                urlsplit(a.get("src", "")).hostname in {
                    "www.topparfuemerie.de", "fooddrinkssuppliers.com"
                }
            ]
            if len(found) != 1:
                raise ValueError("exact_registered_original_missing_or_duplicate_" + slug)
            if not parsed.original_elements:
                raise ValueError("approved_original_not_marked_" + slug)
            if not any(a.get("data-dufynd-original-photo") in {"", "true"} for a in parsed.original_elements):
                raise ValueError("approved_original_marker_incorrect_" + slug)
            if not parsed.title or not parsed.canonicals:
                raise ValueError("public_meta_or_canonical_missing_" + slug)
            if "noindex" in " ".join(parsed.meta_robots).lower():
                raise ValueError("public_fragrance_accidentally_noindexed_" + slug)
            results.append({
                "product_id": pid, "slug": slug, "image_filename": file_name,
                "status": "exact_registered_original_in_public_html",
                "canonical_count": len(parsed.canonicals),
            })
        except Exception as error:
            print("LIVE_PHOTO_QA_FAIL="+json.dumps({"product_id":pid,"slug":slug,
                "type":type(error).__name__,"reason":str(error)[:160]}))
            return 2
    report = {
        "status": "PASS", "public_html_photo_count": len(results),
        "expected_product_head": PROD_SHA,
        "checked_at": datetime.now(UTC).isoformat(),
        "note": "Server-rendered HTML only; external image pixel decoding and shopping clickout intentionally not tested.",
        "live_profiles": results, "merchant_clickouts": 0, "production_writes": 0,
    }
    print("LIVE_PHOTO_QA_SUCCESS="+json.dumps(report,ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
