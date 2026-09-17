from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Literal


FeedFormat = Literal["auto", "json", "csv"]


def detect_feed_format(path: Path) -> str:
    suffix = path.suffix.strip().casefold()

    if suffix == ".json":
        return "json"

    if suffix == ".csv":
        return "csv"

    raise ValueError(
        f"Unsupported merchant feed format: {suffix or '<none>'}"
    )


def _read_feed_text(path: Path) -> str:
    payload = path.read_bytes()

    if not payload:
        raise ValueError(
            "Merchant feed file is empty"
        )

    for encoding in (
        "utf-8-sig",
        "cp1252",
    ):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError(
        "Merchant feed encoding is unsupported"
    )


def _read_json_rows(path: Path) -> list[dict]:
    raw = json.loads(
        _read_feed_text(path)
    )

    if isinstance(raw, list):
        rows = raw
    elif (
        isinstance(raw, dict)
        and isinstance(raw.get("offers"), list)
    ):
        rows = raw["offers"]
    else:
        raise ValueError(
            "JSON merchant feed must be a list or "
            "an object containing an 'offers' list"
        )

    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(
            "Every merchant feed row must be an object"
        )

    return rows


def _detect_csv_dialect(text: str) -> csv.Dialect:
    sample = text[:65536]

    try:
        return csv.Sniffer().sniff(
            sample,
            delimiters=",;\t",
        )
    except csv.Error as exc:
        raise ValueError(
            "Could not detect CSV merchant feed delimiter"
        ) from exc


def _read_csv_rows(path: Path) -> list[dict]:
    text = _read_feed_text(path)
    dialect = _detect_csv_dialect(text)

    reader = csv.DictReader(
        io.StringIO(text),
        dialect=dialect,
    )

    if not reader.fieldnames:
        raise ValueError(
            "CSV merchant feed must contain a header row"
        )

    if any(
        name is None or not name.strip()
        for name in reader.fieldnames
    ):
        raise ValueError(
            "CSV merchant feed contains an empty header"
        )

    return [
        dict(row)
        for row in reader
        if any(
            value is not None and value.strip()
            for value in row.values()
        )
    ]


def read_merchant_feed_rows(
    path: Path,
    *,
    feed_format: FeedFormat = "auto",
) -> list[dict]:
    resolved_format = (
        detect_feed_format(path)
        if feed_format == "auto"
        else feed_format
    )

    if resolved_format == "json":
        return _read_json_rows(path)

    if resolved_format == "csv":
        return _read_csv_rows(path)

    raise ValueError(
        f"Unsupported merchant feed format: {resolved_format}"
    )
