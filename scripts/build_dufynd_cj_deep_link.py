from __future__ import annotations

import argparse
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

DEFAULT_TRACKING_BASE = "https://www.jdoqocy.com/click-101884613-12260695"
ALLOWED_TRACKING_HOSTS = {"www.jdoqocy.com"}
ALLOWED_DESTINATION_HOSTS = {"notino.de", "www.notino.de"}


def _validate_https_url(
    value: str,
    *,
    field: str,
    allowed_hosts: set[str],
) -> str:
    normalized = value.strip()
    parsed = urlparse(normalized)

    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{field} must be an absolute https URL")
    if parsed.username or parsed.password:
        raise ValueError(f"{field} must not contain URL credentials")
    if parsed.hostname not in allowed_hosts:
        raise ValueError(f"{field} host must be one of: " + ", ".join(sorted(allowed_hosts)))

    return normalized


def build_cj_deep_link(
    *,
    destination_url: str,
    tracking_base: str = DEFAULT_TRACKING_BASE,
) -> str:
    destination = _validate_https_url(
        destination_url,
        field="destination_url",
        allowed_hosts=ALLOWED_DESTINATION_HOSTS,
    )
    tracking = _validate_https_url(
        tracking_base,
        field="tracking_base",
        allowed_hosts=ALLOWED_TRACKING_HOSTS,
    )

    parsed_tracking = urlparse(tracking)
    query = dict(parse_qsl(parsed_tracking.query, keep_blank_values=True))
    query["url"] = destination

    return urlunparse(
        parsed_tracking._replace(
            query=urlencode(query),
            fragment="",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a guarded CJ deep link for the verified DUFYND / NOTINO.de tracking route."
        )
    )
    parser.add_argument("--destination-url", required=True)
    parser.add_argument(
        "--tracking-base",
        default=DEFAULT_TRACKING_BASE,
    )
    args = parser.parse_args()

    try:
        url = build_cj_deep_link(
            destination_url=args.destination_url,
            tracking_base=args.tracking_base,
        )
    except ValueError as exc:
        parser.error(str(exc))

    print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
