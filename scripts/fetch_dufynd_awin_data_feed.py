from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

DEFAULT_LIST_MAX_BYTES = 8 * 1024 * 1024
DEFAULT_FEED_MAX_BYTES = 128 * 1024 * 1024
ALLOWED_FEED_HOSTS = {
    "datafeed.api.productserve.com",
    "productdata.awin.com",
}


def _normalize_header(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


def _row_value(row: dict[str, str], *aliases: str) -> str:
    normalized = {_normalize_header(key): str(value or "").strip() for key, value in row.items()}
    for alias in aliases:
        value = normalized.get(_normalize_header(alias), "")
        if value:
            return value
    return ""


def _maybe_decompress(payload: bytes, *, max_bytes: int) -> bytes:
    if payload[:2] == bytes((0x1F, 0x8B)):
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as compressed:
            expanded = compressed.read(max_bytes + 1)
        if len(expanded) > max_bytes:
            raise ValueError("awin_response_exceeds_max_bytes")
        return expanded
    if len(payload) > max_bytes:
        raise ValueError("awin_response_exceeds_max_bytes")
    return payload


def parse_feed_list(
    payload: bytes, *, max_bytes: int = DEFAULT_LIST_MAX_BYTES
) -> list[dict[str, str]]:
    decoded = _maybe_decompress(payload, max_bytes=max_bytes).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(decoded)))


def find_feed(
    rows: list[dict[str, str]],
    *,
    advertiser_id: str,
    feed_id: str,
) -> dict[str, str]:
    for row in rows:
        if (
            _row_value(row, "Advertiser ID") == advertiser_id
            and _row_value(row, "Feed ID") == feed_id
        ):
            return row
    raise ValueError("target_awin_feed_not_found")


def sanitized_feed_metadata(row: dict[str, str]) -> dict[str, str | bool]:
    membership = _row_value(row, "Membership Status")
    download_url = _row_value(row, "URL")
    parsed = urlparse(download_url)
    return {
        "advertiser_id": _row_value(row, "Advertiser ID"),
        "advertiser_name": _row_value(row, "Advertiser Name"),
        "feed_id": _row_value(row, "Feed ID"),
        "feed_name": _row_value(row, "Feed Name"),
        "membership_status": membership,
        "joined": membership.casefold() == "joined",
        "language": _row_value(row, "Language"),
        "primary_region": _row_value(row, "Primary Region"),
        "last_imported": _row_value(row, "Last Imported"),
        "download_host": parsed.hostname or "",
    }


def _read_url(url: str, *, max_bytes: int) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "DUFYND-Awin-Feed-Revalidator/1.0",
            "Accept": "*/*",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("awin_response_exceeds_max_bytes")
                chunks.append(chunk)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("awin_request_failed") from exc
    return b"".join(chunks)


def download_feed_from_list(
    *,
    api_key: str,
    advertiser_id: str,
    feed_id: str,
    output_path: Path | None,
    report_path: Path | None,
    list_max_bytes: int = DEFAULT_LIST_MAX_BYTES,
    feed_max_bytes: int = DEFAULT_FEED_MAX_BYTES,
) -> dict:
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("awin_data_feed_api_key_required")

    list_url = "https://productdata.awin.com/datafeed/list/apikey/" + quote(api_key, safe="")
    rows = parse_feed_list(_read_url(list_url, max_bytes=list_max_bytes), max_bytes=list_max_bytes)
    row = find_feed(rows, advertiser_id=advertiser_id, feed_id=feed_id)
    metadata = sanitized_feed_metadata(row)

    if not metadata["joined"]:
        raise ValueError("awin_program_membership_not_joined")

    download_url = _row_value(row, "URL")
    parsed = urlparse(download_url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_FEED_HOSTS:
        raise ValueError("awin_feed_download_host_not_allowed")

    report = {
        "version": 1,
        "checked_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source": "awin_product_feed_list",
        **metadata,
        "downloaded": False,
        "downloaded_bytes": 0,
        "secrets_logged": False,
    }

    if output_path is not None:
        feed_payload = _maybe_decompress(
            _read_url(download_url, max_bytes=feed_max_bytes), max_bytes=feed_max_bytes
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(feed_payload)
        report["downloaded"] = True
        report["downloaded_bytes"] = len(feed_payload)

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read the current Awin product-feed list and optionally download one "
            "exact feed without printing API keys or secret-bearing download URLs."
        )
    )
    parser.add_argument(
        "--api-key-env",
        default="AWIN_DATA_FEED_API_KEY",
        help="Environment variable holding the Awin data-feed API key.",
    )
    parser.add_argument("--advertiser-id", default="31081")
    parser.add_argument("--feed-id", default="91379")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env, "")

    try:
        report = download_feed_from_list(
            api_key=api_key,
            advertiser_id=str(args.advertiser_id),
            feed_id=str(args.feed_id),
            output_path=args.output,
            report_path=args.report,
        )
    except (OSError, ValueError, RuntimeError, UnicodeDecodeError, csv.Error) as exc:
        parser.error(str(exc))

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "DUFYND Awin feed revalidation | "
            f"advertiser={report['advertiser_id']} | "
            f"feed={report['feed_id']} | "
            f"joined={report['joined']} | "
            f"last_imported={report['last_imported'] or 'unknown'} | "
            f"downloaded={report['downloaded']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
