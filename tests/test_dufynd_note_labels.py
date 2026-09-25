"""Keep all catalog fragrance taxonomy covered by German display labels."""

from __future__ import annotations

import json
import re
from pathlib import Path

CATALOG = Path("examples/retail/data/scentai_products.json")
LABELS = Path("examples/retail/storefront-web/lib/noteLabels.ts")
DETAIL_PAGE = Path("examples/retail/storefront-web/app/duft/[slug]/page.tsx")
CATALOG_BROWSER = Path("examples/retail/storefront-web/components/FragranceCatalogBrowser.tsx")

JSON_ENTRY = re.compile(
    r'^\s*"(?P<key>[^"]+)":\s*"(?P<label>[^"]+)",\s*$',
    re.MULTILINE,
)
TS_ENTRY = re.compile(
    r'^\s*(?P<key>[A-Za-z0-9_]+):\s*"(?P<label>[^"]+)",\s*$',
    re.MULTILINE,
)


def test_all_catalog_notes_have_german_display_labels() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    notes: set[str] = set()

    for product in catalog["products"]:
        for values in (product.get("notes") or {}).values():
            if isinstance(values, list):
                notes.update(str(value).strip().lower() for value in values if str(value).strip())

    source = LABELS.read_text(encoding="utf-8")
    labels = {match["key"]: match["label"] for match in JSON_ENTRY.finditer(source)}

    missing = sorted(notes - labels.keys())
    assert not missing, f"Missing German note labels: {missing}"
    assert all(labels[note].strip() for note in notes)


def test_all_catalog_accords_and_targets_have_german_ui_labels() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog_accords: set[str] = set()
    catalog_targets: set[str] = set()

    for product in catalog["products"]:
        profile = product.get("fragrance_profile") or {}
        catalog_accords.update(
            str(value).strip().lower()
            for value in profile.get("community_accords", [])
            if str(value).strip()
        )

        classification = product.get("classification") or {}
        catalog_targets.update(
            str(value).strip().lower()
            for value in classification.get("scentai_target_groups", [])
            if str(value).strip()
        )

    detail_entries = {
        match["key"]: match["label"]
        for match in TS_ENTRY.finditer(DETAIL_PAGE.read_text(encoding="utf-8"))
    }
    catalog_entries = {
        match["key"]: match["label"]
        for match in TS_ENTRY.finditer(CATALOG_BROWSER.read_text(encoding="utf-8"))
    }

    missing_detail_accords = sorted(catalog_accords - detail_entries.keys())
    missing_catalog_accords = sorted(catalog_accords - catalog_entries.keys())
    missing_targets = sorted(catalog_targets - detail_entries.keys())

    assert not missing_detail_accords, (
        f"Missing German detail accord labels: {missing_detail_accords}"
    )
    assert not missing_catalog_accords, (
        f"Missing German catalog accord labels: {missing_catalog_accords}"
    )
    assert not missing_targets, f"Missing German target labels: {missing_targets}"
