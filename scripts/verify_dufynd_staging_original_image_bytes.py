"""Hash unchanged official Awin-fed packshots for private, zero-click review.

Fixed four-source allowlist from current Top Parfuemerie feed run 40472385765.
No affiliate clickouts, images saved, artifacts uploaded, or public approvals.
No redirects, unsafe hosts, oversized downloads, HTML or content rewriting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_IMAGE_BYTES = 2 * 1024 * 1024
FILES = (
    ("SC-JPG-LE-MALE-LE-PARFUM-125", "867108", "8435415032315",
     "https://www.topparfuemerie.de/media/catalog/product/8/6/867108_8435415032315_051.png"),
    ("SC-NARCISO-RODRIGUEZ-PURE-MUSC-EDP-100", "850706", "3423478515956",
     "https://www.topparfuemerie.de/media/catalog/product/8/5/850706_3423478515956_061.png"),
    ("SC-HUGO-BOSS-BOTTLED-ABSOLU-100", "924267", "3616305480620",
     "https://www.topparfuemerie.de/media/catalog/product/9/2/924267_3616305480620_051.png"),
    ("SC-AMOUAGE-GUIDANCE-46-EXTRAIT-100", "924069", "0701666410980",
     "https://www.topparfuemerie.de/media/catalog/product/9/2/924069_701666410980_051.png"),
)
PNG_PREFIX = b"\x89PNG\r\n\x1a\n"
PATH = re.compile(r"/media/catalog/product/(?:[0-9a-z]/){2}([0-9]+)_([0-9]+)_[0-9]+\.png")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirect_not_allowed")


def validate_source(url: str, expected_sku: str, gtin: str) -> None:
    u = urlsplit(url)
    if (
        u.scheme != "https" or u.netloc != "www.topparfuemerie.de"
        or u.query or u.fragment or u.username or u.password or u.port
    ):
        raise ValueError("source_host_not_allowed")
    match = PATH.fullmatch(u.path)
    if (
        not match or match.group(1) != expected_sku
        or match.group(2).lstrip("0") != gtin.lstrip("0")
    ):
        raise ValueError("source_variant_filename_mismatch")


def png_dimensions(payload: bytes) -> tuple[int, int]:
    if len(payload) < 33 or not payload.startswith(PNG_PREFIX):
        raise ValueError("invalid_png_signature_or_length")
    if payload[12:16] != b"IHDR" or payload[8:12] != b"\x00\x00\x00\x0d":
        raise ValueError("invalid_png_ihdr")
    width, height = struct.unpack(">II", payload[16:24])
    if not 32 <= width <= 4000 or not 32 <= height <= 4000:
        raise ValueError("invalid_png_dimensions")
    return width, height


def verify_file(product_id: str, sku: str, gtin: str, url: str) -> dict:
    record = {
        "product_id": product_id, "merchant_sku": sku,
        "historically_corroborated_gtin": gtin, "source_url": url,
        "scope": "PRIVATE_IMAGE_BYTES_REVIEW_ONLY",
    }
    try:
        validate_source(url, sku, gtin)
        request = Request(url, headers={
            "User-Agent": "DUFYND-Awin-OriginalReview/1.0",
            "Accept": "image/png",
        })
        with build_opener(NoRedirect()).open(request, timeout=12) as response:
            if response.geturl() != url or response.status != 200:
                raise ValueError("source_response_mismatch")
            if response.headers.get("Content-Type", "").split(";")[0].strip() != "image/png":
                raise ValueError("source_mime_mismatch")
            data = response.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError("image_too_large")
        width, height = png_dimensions(data)
        record.update({
            "status": "SOURCE_BYTES_HASH_VERIFIED",
            "downloaded_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "width": width, "height": height, "bytes_modified": False,
            "owner_visual_approval": False, "image_publication_allowed": False,
            "merchant_variant_current_selection_not_verified": True,
        })
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        record.update({
            "status": "HOLD_SOURCE_IMAGE_NOT_VERIFIED",
            "reason": "http_status_" + str(exc.code) if isinstance(exc, HTTPError)
                    else type(exc).__name__ + "_no_bytes",
            "owner_visual_approval": False, "image_publication_allowed": False,
        })
    return record


def self_test():
    tiny_png = PNG_PREFIX + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", 120, 600) + b"\x08\x02\x00\x00\x00" + b"\x00\x00\x00\x00"
    assert png_dimensions(tiny_png) == (120, 600)
    assert len(FILES) == 4
    for _, sku, gtin, url in FILES:
        validate_source(url, sku, gtin)
        for bad in (url.replace("https://", "http://"), url + "?x=1",
                    url.replace(sku + "_", "999_")):
            try:
                validate_source(bad, sku, gtin)
            except ValueError:
                pass
            else:
                raise AssertionError("source_guard_failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    self_test()
    if args.self_test:
        print("staging_image_hash_source_guards: passed")
        return 0
    receipts = [verify_file(*item) for item in FILES]
    result = {
        "schema_version": 1,
        "status": "SOURCE_BYTES_REVIEW_ONLY",
        "source_run": 40472385765,
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "receipts": receipts,
        "verified_originals": sum(r["status"] == "SOURCE_BYTES_HASH_VERIFIED" for r in receipts),
        "approved_public_images": 0,
        "registered_offers": 0,
        "affiliate_clickouts": 0,
        "image_artifacts_uploaded": 0,
    }
    print("DUFYND_STAGING_IMAGE_BYTE_RECEIPTS=" + json.dumps(result, ensure_ascii=True))
    return 0 if result["verified_originals"] == 4 else 2


if __name__ == "__main__":
    sys.exit(main())
