from __future__ import annotations

import argparse
import os
import re
from urllib.parse import urlencode, urljoin, urlparse

ALLOWED_CHANNELS = {
    "tiktok",
    "instagram",
    "youtube",
    "organic",
    "newsletter",
    "partner",
}
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")
LANDING_PATTERN = re.compile(r"^/[A-Za-z0-9/_-]*$")


def validate_identifier(value: str, *, label: str) -> str:
    normalized = value.strip()
    if not IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ValueError(
            f"{label} must be a 1-80 character identifier using only "
            "letters, numbers, dot, underscore, colon or hyphen"
        )
    return normalized


def build_campaign_url(
    *,
    base_url: str,
    landing_path: str,
    channel: str,
    campaign_id: str,
    content_id: str,
) -> str:
    parsed_base = urlparse(base_url.strip())
    if (
        parsed_base.scheme != "https"
        or not parsed_base.netloc
        or parsed_base.username
        or parsed_base.password
    ):
        raise ValueError("base_url must be a public HTTPS origin without credentials")

    landing = landing_path.strip()
    if not LANDING_PATTERN.fullmatch(landing):
        raise ValueError(
            "landing_path must be an absolute site path without query parameters or fragments"
        )

    normalized_channel = channel.strip().casefold()
    if normalized_channel not in ALLOWED_CHANNELS:
        supported = ", ".join(sorted(ALLOWED_CHANNELS))
        raise ValueError(f"Unsupported channel {channel!r}. Supported: {supported}")

    campaign = validate_identifier(
        campaign_id,
        label="campaign_id",
    )
    content = validate_identifier(
        content_id,
        label="content_id",
    )

    target = urljoin(
        base_url.rstrip("/") + "/",
        landing.lstrip("/"),
    )
    query = urlencode(
        {
            "src": normalized_channel,
            "cmp": campaign,
            "content": content,
        }
    )
    return f"{target}?{query}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a privacy-safe DUFYND launch link with standardized "
            "channel, campaign and content attribution."
        )
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("NEXT_PUBLIC_SITE_URL", ""),
    )
    parser.add_argument("--landing", required=True)
    parser.add_argument(
        "--channel",
        choices=sorted(ALLOWED_CHANNELS),
        required=True,
    )
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--content", required=True)
    args = parser.parse_args()

    if not args.base_url:
        parser.error("--base-url or NEXT_PUBLIC_SITE_URL is required")

    try:
        link = build_campaign_url(
            base_url=args.base_url,
            landing_path=args.landing,
            channel=args.channel,
            campaign_id=args.campaign,
            content_id=args.content,
        )
    except ValueError as exc:
        parser.error(str(exc))

    print(link)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
