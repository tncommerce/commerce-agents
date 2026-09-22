from __future__ import annotations

import csv
import gzip
import io
import json
from pathlib import Path
from typing import Literal

FeedFormat = Literal["auto", "json", "csv"]

DEFAULT_MAX_FEED_BYTES = 100 * 1024 * 1024
DEFAULT_MAX_FEED_ROWS = 500_000


def _normalized_suffixes(path: Path) -> list[str]:
    return [suffix.strip().casefold() for suffix in path.suffixes]


def _is_gzip_path(path: Path) -> bool:
    return bool(_normalized_suffixes(path)) and _normalized_suffixes(path)[-1] == ".gz"


def detect_feed_format(path: Path) -> str:
    suffixes = _normalized_suffixes(path)

    if suffixes[-2:] == [".json", ".gz"] or suffixes[-1:] == [".json"]:
        return "json"

    if suffixes[-2:] == [".csv", ".gz"] or suffixes[-1:] == [".csv"]:
        return "csv"

    suffix = path.suffix.strip().casefold()
    raise ValueError(f"Unsupported merchant feed format: {suffix or '<none>'}")


def _enforce_file_size(
    path: Path,
    *,
    max_bytes: int,
) -> None:
    size = path.stat().st_size

    if size > max_bytes:
        raise ValueError(
            f"Merchant feed exceeds maximum file size: {size} bytes > {max_bytes} bytes"
        )


def _read_file_payload(
    path: Path,
    *,
    max_bytes: int,
) -> bytes:
    _enforce_file_size(
        path,
        max_bytes=max_bytes,
    )

    if not _is_gzip_path(path):
        return path.read_bytes()

    try:
        with gzip.open(path, "rb") as handle:
            payload = handle.read(max_bytes + 1)
    except (gzip.BadGzipFile, OSError, EOFError) as exc:
        raise ValueError("Merchant feed gzip payload is invalid") from exc

    if len(payload) > max_bytes:
        raise ValueError(
            "Merchant feed exceeds maximum decompressed file size: "
            f">{max_bytes} bytes"
        )

    return payload


def _read_feed_text(
    path: Path,
    *,
    max_bytes: int,
) -> str:
    payload = _read_file_payload(
        path,
        max_bytes=max_bytes,
    )

    if not payload:
        raise ValueError("Merchant feed file is empty")

    for encoding in (
        "utf-8-sig",
        "cp1252",
    ):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError("Merchant feed encoding is unsupported")


def _read_json_rows(
    path: Path,
    *,
    max_bytes: int,
    max_rows: int,
) -> list[dict]:
    raw = json.loads(
        _read_feed_text(
            path,
            max_bytes=max_bytes,
        )
    )

    if isinstance(raw, list):
        rows = raw
    elif isinstance(raw, dict) and isinstance(raw.get("offers"), list):
        rows = raw["offers"]
    else:
        raise ValueError(
            "JSON merchant feed must be a list or an object containing an 'offers' list"
        )

    if len(rows) > max_rows:
        raise ValueError(f"Merchant feed exceeds maximum row count: {len(rows)} > {max_rows}")

    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("Every merchant feed row must be an object")

    return rows


def _detect_csv_dialect(text: str) -> csv.Dialect:
    sample = text[:65536]

    try:
        return csv.Sniffer().sniff(
            sample,
            delimiters=",;\t",
        )
    except csv.Error as exc:
        raise ValueError("Could not detect CSV merchant feed delimiter") from exc


def _read_csv_rows(
    path: Path,
    *,
    max_bytes: int,
    max_rows: int,
) -> list[dict]:
    text = _read_feed_text(
        path,
        max_bytes=max_bytes,
    )
    dialect = _detect_csv_dialect(text)

    reader = csv.DictReader(
        io.StringIO(text),
        dialect=dialect,
    )

    if not reader.fieldnames:
        raise ValueError("CSV merchant feed must contain a header row")

    if any(name is None or not name.strip() for name in reader.fieldnames):
        raise ValueError("CSV merchant feed contains an empty header")

    rows: list[dict] = []

    for row in reader:
        if not any(value is not None and value.strip() for value in row.values()):
            continue

        rows.append(dict(row))

        if len(rows) > max_rows:
            raise ValueError(f"Merchant feed exceeds maximum row count: >{max_rows}")

    return rows


def read_merchant_feed_rows(
    path: Path,
    *,
    feed_format: FeedFormat = "auto",
    max_bytes: int = DEFAULT_MAX_FEED_BYTES,
    max_rows: int = DEFAULT_MAX_FEED_ROWS,
) -> list[dict]:
    if max_bytes < 1:
        raise ValueError("max_bytes must be at least 1")

    if max_rows < 1:
        raise ValueError("max_rows must be at least 1")

    resolved_format = detect_feed_format(path) if feed_format == "auto" else feed_format

    if resolved_format == "json":
        return _read_json_rows(
            path,
            max_bytes=max_bytes,
            max_rows=max_rows,
        )

    if resolved_format == "csv":
        return _read_csv_rows(
            path,
            max_bytes=max_bytes,
            max_rows=max_rows,
        )

    raise ValueError(f"Unsupported merchant feed format: {resolved_format}")
