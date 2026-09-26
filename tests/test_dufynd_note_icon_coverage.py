"""Keep DUFYND catalog notes mapped to a deliberate visual motif."""

from __future__ import annotations

import json
import re
from pathlib import Path

CATALOG = Path("examples/retail/data/scentai_products.json")
STAGING = Path("examples/retail/data/scentai_catalog_staging.json")
ICONS = Path("examples/retail/storefront-web/components/NoteIcon.tsx")

MOTIF_ENTRY = re.compile(
    r'\{ motif: "[^"]+", names: \[(?P<names>[^\]]*)\] \}',
    re.MULTILINE,
)
QUOTED = re.compile(r'"([^"]+)"')


def test_all_catalog_notes_have_a_specific_icon_motif() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    notes: set[str] = set()

    for product in catalog["products"]:
        for values in (product.get("notes") or {}).values():
            if isinstance(values, list):
                notes.update(str(value).strip().lower() for value in values if str(value).strip())

    source = ICONS.read_text(encoding="utf-8")
    motif_terms = [
        term.lower()
        for match in MOTIF_ENTRY.finditer(source)
        for term in QUOTED.findall(match["names"])
    ]

    assert motif_terms, "No DUFYND note-icon motif terms found"

    unmapped = sorted(note for note in notes if not any(term in note for term in motif_terms))

    assert not unmapped, f"Catalog notes fell back to the generic icon: {unmapped}"


def test_all_staging_notes_have_an_intentional_icon_motif() -> None:
    staging = json.loads(STAGING.read_text(encoding="utf-8"))
    notes: set[str] = set()

    for product in staging["products"]:
        profile = product.get("fragrance_profile") or {}
        notes.update(
            str(value).strip().lower()
            for value in profile.get("key_notes", [])
            if str(value).strip()
        )
        for values in (product.get("notes") or {}).values():
            if isinstance(values, list):
                notes.update(
                    str(value).strip().lower()
                    for value in values
                    if str(value).strip()
                )

    source = ICONS.read_text(encoding="utf-8")
    motif_terms = [
        term.lower()
        for match in MOTIF_ENTRY.finditer(source)
        for term in QUOTED.findall(match["names"])
    ]

    unmapped = sorted(
        note for note in notes if not any(term in note for term in motif_terms)
    )

    assert not unmapped, f"Staging notes fell back to the generic icon: {unmapped}"


def test_hedione_is_explicitly_abstract_not_accidental_fallback() -> None:
    source = ICONS.read_text(encoding="utf-8")
    assert '{ motif: "abstract", names: ["hedione"] }' in source
