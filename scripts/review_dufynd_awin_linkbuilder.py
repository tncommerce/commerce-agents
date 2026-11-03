"""One-shot, private, official Awin Publisher Link Builder verification.

NO clickout, offer activation, network reporting, or deployment. A publisher
OAuth2 API token is distinct from the Awin Product Data Feed key. This script
never manufactures affiliate links and never prints the returned URL.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

PUBLISHER_ID = 3099222
ADVERTISER_ID = 11672
DESTINATION = "https://www.perfumetrader.de/de/paco-rabanne-1-million-eau-de-toilette-100-ml"
CLICKREF = "one_million_example61_01"
API_HOST = "api.awin.com"
API_PATH = f"/publishers/{PUBLISHER_ID}/linkbuilder/generate"
TOKEN_ENV = "AWIN_PUBLISHER_API_TOKEN"
MAX_RESPONSE_BYTES = 65_536


class VerificationError(ValueError):
    """Safe, non-secret error suitable for console output."""


def request_body() -> dict:
    return {
        "advertiserId": ADVERTISER_ID,
        "destinationUrl": DESTINATION,
        "parameters": {"clickref": CLICKREF},
        "shorten": False,
    }


def verify_generated_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 4096:
        raise VerificationError("invalid_linkbuilder_url")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.awin1.com"
        or parsed.port is not None
        or parsed.username
        or parsed.password
        or parsed.path != "/cread.php"
        or parsed.fragment
    ):
        raise VerificationError("invalid_linkbuilder_url")
    params = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    required = {
        "awinmid": str(ADVERTISER_ID),
        "awinaffid": str(PUBLISHER_ID),
        "clickref": CLICKREF,
    }
    for key, val in required.items():
        if params.get(key) != [val]:
            raise VerificationError("linkbuilder_identity_mismatch")
    if params.get("ued") != [DESTINATION] and params.get("p") != [DESTINATION]:
        raise VerificationError("linkbuilder_destination_mismatch")
    return url


def fetch_from_awin(token: str) -> dict:
    if not token or not token.strip() or any(c in token for c in "\r\n"):
        raise VerificationError("publisher_api_token_missing_or_invalid")
    payload = json.dumps(request_body(), separators=(",", ":")).encode("utf-8")
    connection = http.client.HTTPSConnection(API_HOST, timeout=12)
    try:
        connection.request(
            "POST",
            API_PATH,
            body=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        response = connection.getresponse()
        if response.status != 200:
            raise VerificationError("awin_linkbuilder_non_200")
        data = response.read(MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES:
            raise VerificationError("awin_linkbuilder_oversized_response")
        try:
            decoded = json.loads(data)
        except (ValueError, UnicodeDecodeError) as exc:
            raise VerificationError("awin_linkbuilder_invalid_json") from exc
        if not isinstance(decoded, dict):
            raise VerificationError("awin_linkbuilder_invalid_json")
        verify_generated_url(decoded.get("url"))
        return decoded
    except (OSError, TimeoutError) as exc:
        raise VerificationError("awin_linkbuilder_transport_failed") from exc
    finally:
        connection.close()


def write_private_receipt(path: Path, result: dict) -> dict:
    url = verify_generated_url(result.get("url"))
    if path.exists() or path.is_symlink():
        raise VerificationError("receipt_path_exists")
    if not path.parent.is_dir():
        raise VerificationError("receipt_parent_missing")
    receipt = {
        "scope": "private_official_awin_linkbuilder_receipt",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "publisher_id": PUBLISHER_ID,
        "advertiser_id": ADVERTISER_ID,
        "destination_url": DESTINATION,
        "clickref": CLICKREF,
        "generated_url": url,
        "generated_url_sha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
        "evidence": "Awin Publisher API HTTP 200, exact returned URL, no redirect followed",
        "not_verified": [
            "merchant_redirect",
            "live_checkout",
            "commission",
            "picture_rights",
            "offer_price",
        ],
        "production_activated": False,
    }
    data = (json.dumps(receipt, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return {
        "status": "OFFICIAL_LINK_GENERATED_PRIVATE",
        "sha256": receipt["generated_url_sha256"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bounded private Rabanne Awin Link Builder verification, no clickout"
    )
    parser.add_argument(
        "--execute", action="store_true", help="One authorized Awin API POST (no retries)"
    )
    parser.add_argument("--output", type=Path, help="New private receipt file (never overwrite)")
    args = parser.parse_args(argv)
    if not args.execute:
        print(
            json.dumps(
                {
                    "status": "DRY_RUN_ONLY",
                    "api_path": API_PATH,
                    "body": request_body(),
                    "writes": 0,
                }
            )
        )
        return 0
    if args.output is None:
        parser.error("--output is required with --execute")
    if args.output.exists() or args.output.is_symlink() or not args.output.parent.is_dir():
        parser.error("--output must be an unused path within an existing private directory")
    try:
        token = os.environ.get(TOKEN_ENV, "")
        generated = fetch_from_awin(token)
        safe = write_private_receipt(args.output, generated)
    except VerificationError as exc:
        parser.error(str(exc))
    print(json.dumps(safe))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
