from __future__ import annotations

import csv
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


def _read_json_rows(path: Path) -> list[dict]:
    raw = json.loads(
        path.read_text(encoding="utf-8-sig")
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


def _read_csv_rows(path: Path) -> list[dict]:
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise ValueError(
                "CSV merchant feed must contain a header row"
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
