"""Keep DUFYND catalog notes mapped to a deliberate visual motif."""

from __future__ import annotations

import json
import re
from pathlib import Path

CATALOG = Path("examples/retail/data/scentai_products.json")
ICONS = Path("examples/retail/storefront-web/components/NoteIcon.tsx")

MOTIF_ENTRY = re.compile(
    r'\{ motif: "(?P<motif>[^"]+)", names: \[(?P<names>[^\]]*)\] \}',
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


def test_priority_notes_use_distinct_premium_motifs() -> None:
    source = ICONS.read_text(encoding="utf-8")
    mappings = {
        term.lower(): match["motif"]
        for match in MOTIF_ENTRY.finditer(source)
        for term in QUOTED.findall(match["names"])
    }

    expected = {
        "bergamot": "bergamot",
        "grapefruit": "grapefruit",
        "jasmine": "jasmine",
        "patchouli": "patchouli",
        "lavender": "lavender",
        "tonka bean": "tonka",
        "vanilla": "vanilla",
        "spices": "spice",
        "musk": "musk",
        "guaiac wood": "wood",
        "amber": "amber",
        "mandarin": "mandarin",
        "lemon": "lemon",
        "geranium": "geranium",
        "apple": "apple",
        "leather": "leather",
        "incense": "incense",
        "pink pepper": "pepper",
    }

    assert {note: mappings.get(note) for note in expected} == expected


def test_priority_premium_motifs_are_not_monochrome_current_color_only() -> None:
    source = ICONS.read_text(encoding="utf-8")
    for motif in (
        "bergamot",
        "grapefruit",
        "jasmine",
        "patchouli",
        "lavender",
        "tonka",
        "wood",
        "amber",
        "musk",
        "mandarin",
        "lemon",
        "geranium",
        "apple",
        "leather",
        "incense",
        "pepper",
    ):
        block_start = source.index(f"  {motif}: (")
        block_end = source.index("\n  ),", block_start)
        block = source[block_start:block_end]
        assert 'fill="#' in block, f"{motif} lost its colored ingredient artwork"

    for motif in ("vanilla", "spice"):
        block_start = source.index(f"  {motif}: (")
        block_end = source.index("\n  ),", block_start)
        block = source[block_start:block_end]
        assert 'fill="#' in block or 'stroke="#' in block, (
            f"{motif} lost its colored ingredient artwork"
        )
