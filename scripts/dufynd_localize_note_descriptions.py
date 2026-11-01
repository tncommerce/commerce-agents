#!/usr/bin/env python3
"""Check or refresh German display copy from approved, unchanged source notes.

No new note, product image, price, offer or public approval is generated here.
The original review packets remain separate from the public release gate.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "examples/retail/data"
WEB = ROOT / "examples/retail/storefront-web"
LABELS = WEB / "lib/noteLabels.ts"
RELEASED = WEB / "lib/generated/released-profiles.json"
WAVES = [
    DATA / "dufynd_facts_wave_01_review.json",
    DATA / "dufynd_facts_wave_02_review.json",
]
GROUPS = [
    ("top", "Kopfnoten"),
    ("heart", "Herznoten"),
    ("base", "Basisnoten"),
    ("key", "Dokumentierte Duftnoten"),
]
DISCLAIMER = "Die vorhandenen Angaben werden nicht als vollständige Duftpyramide ausgegeben."


def labels() -> dict[str, str]:
    result: dict[str, str] = {}
    for line in LABELS.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r'\s*"([^"]+)":\s*"([^"]+)",\s*', line)
        if match:
            key, value = match.groups()
            key = key.strip().lower()
            if key in result:
                raise ValueError(f"Duplicate German label: {key}")
            result[key] = value
    if len(result) < 200:
        raise ValueError("German note label registry could not be parsed")
    return result


def localized_description(row: dict, translations: dict[str, str]) -> str:
    notes = row["notes"]
    if not isinstance(row.get("summary_de"), str) or not row["summary_de"].strip():
        raise ValueError("Missing source-bound German summary")
    key_only = bool(notes.get("key"))
    if key_only and any(notes.get(group) for group in ("top", "heart", "base")):
        raise ValueError("Unverified pyramid plus key-note grouping")
    groups = []
    for field, title in GROUPS:
        terms = notes.get(field, [])
        if not isinstance(terms, list):
            raise ValueError(f"Invalid {field} note list")
        if terms:
            translated = []
            for term in terms:
                note = translations.get(term.strip().lower())
                if not note:
                    raise ValueError(f"Missing approved note label: {term}")
                translated.append(note)
            groups.append(f"{title}: {', '.join(translated)}")
    if not groups:
        raise ValueError("No documented note groups")
    result = row["summary_de"].strip() + " " + "; ".join(groups) + "."
    if key_only:
        result += " " + DISCLAIMER
    return result


def update_sources() -> dict[Path, dict]:
    translations = labels()
    files: dict[Path, dict] = {}
    packets = []
    seen: set[str] = set()
    for filename, expected in zip(WAVES, (20, 21), strict=True):
        packet = json.loads(filename.read_text(encoding="utf-8"))
        profiles = packet["profiles"]
        if (
            packet["status"] != "REVIEW_ONLY_NOT_PUBLISHED"
            or len(profiles) != expected
            or packet["profile_count"] != expected
            or packet["public_release_authorized"] is not False
        ):
            raise ValueError(f"Review-only wave altered: {filename.name}")
        for row in profiles:
            product_id = row["product_id"]
            if product_id in seen:
                raise ValueError(f"Duplicate identity: {product_id}")
            seen.add(product_id)
            row["editorial_description_de"] = localized_description(row, translations)
        files[filename] = packet
        packets.append(profiles)
    released = json.loads(RELEASED.read_text(encoding="utf-8"))
    public = released["profiles"]
    first = {row["product_id"]: row for row in packets[0]}
    second = {row["product_id"] for row in packets[1]}
    if len(public) != 20 or set(x["product_id"] for x in public) != set(first):
        raise ValueError("The owner-released 20-profile scope changed")
    if second.intersection(first):
        raise ValueError("Unapproved second wave overlaps first wave")
    for row in public:
        source = first[row["product_id"]]
        if (
            row["notes"] != source["notes"]
            or row["summary_de"] != source["summary_de"]
            or row["seo"] != source["seo"]
            or row["indexing_approved"] is not True
        ):
            raise ValueError("Public facts/SEO/approval drift")
        row["editorial_description_de"] = source["editorial_description_de"]
    files[RELEASED] = released
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    files = update_sources()
    incorrect = []
    for path, value in files.items():
        expected = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            incorrect.append(path.relative_to(ROOT).as_posix())
            if args.write:
                path.write_text(expected, encoding="utf-8")
    if incorrect and not args.write:
        print("German review copy differs; run --write: " + ", ".join(incorrect))
        return 1
    print("German source-bound note descriptions: 20 released + 21 held, all mapped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
