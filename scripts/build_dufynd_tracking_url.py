from __future__ import annotations

import argparse
import re
from urllib.parse import urlencode, urljoin, urlparse, urlunparse

ALLOWED_SOURCES = {
    "tiktok",
    "instagram",
    "youtube",
    "organic",
    "newsletter",
    "partner",
}
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")


def validate_identifier(value: str, *, field: str) -> str:
    normalized = value.strip()
    if not IDENTIFIER_RE.fullmatch(normalized):
        raise ValueError(
            f"{field} must be 1-80 characters using letters, numbers, '.', '_', ':', or '-'"
        )
    return normalized


def build_tracking_url(
    *,
    base_url: str,
    path: str,
    source: str,
    campaign_id: str,
    content_id: str,
) -> str:
    normalized_source = source.strip().casefold()
    if normalized_source not in ALLOWED_SOURCES:
        raise ValueError("source must be one of: " + ", ".join(sorted(ALLOWED_SOURCES)))

    campaign = validate_identifier(
        campaign_id,
        field="campaign_id",
    )
    content = validate_identifier(
        content_id,
        field="content_id",
    )

    parsed_base = urlparse(base_url)
    if parsed_base.scheme != "https" or not parsed_base.netloc:
        raise ValueError("base_url must be an absolute https URL")

    normalized_path = "/" + path.lstrip("/")
    target = urljoin(base_url.rstrip("/") + "/", normalized_path.lstrip("/"))
    parsed = urlparse(target)
    query = urlencode(
        {
            "src": normalized_source,
            "cmp": campaign,
            "content": content,
        }
    )
    return urlunparse(parsed._replace(query=query))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a DUFYND social/content attribution URL.")
    parser.add_argument(
        "--base-url",
        default="https://dufynd.de",
    )
    parser.add_argument(
        "--path",
        default="/",
    )
    parser.add_argument(
        "--source",
        required=True,
        choices=sorted(ALLOWED_SOURCES),
    )
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--content-id", required=True)
    args = parser.parse_args()

    try:
        url = build_tracking_url(
            base_url=args.base_url,
            path=args.path,
            source=args.source,
            campaign_id=args.campaign_id,
            content_id=args.content_id,
        )
    except ValueError as exc:
        parser.error(str(exc))

    print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
