"""DUFYND free comparison must explain only documented scent evidence."""

import json
from pathlib import Path

BASE = Path("examples/retail/storefront-web")
COMPONENT = BASE / "components/FragranceComparisonEvidence.tsx"
PICKER = BASE / "components/FragranceComparisonPicker.tsx"
PRODUCTS = Path("examples/retail/data/scentai_products.json")


def test_free_comparison_renders_evidence_next_to_side_by_side_values():
    source = PICKER.read_text(encoding="utf-8")
    evidence = COMPONENT.read_text(encoding="utf-8")
    assert 'import FragranceComparisonEvidence from "@/components/FragranceComparisonEvidence"' in source
    assert "<FragranceComparisonEvidence left={left} right={right} />" in source
    assert "Was verbindet diese beiden Düfte?" in evidence
    assert "Gemeinsame Duftakkorde" in evidence
    assert "Gemeinsame Duftnoten" in evidence
    assert ": eigene Akzente" in evidence
    assert "sm:grid-cols-2" in evidence


def test_no_inferred_clone_or_fake_percent_matching():
    evidence = COMPONENT.read_text(encoding="utf-8")
    assert "overlappingTerms(leftAccords, rightAccords)" in evidence
    assert "allDocumentedNotes(left)" in evidence
    assert "allDocumentedNotes(right)" in evidence
    assert "normalizedTerm" in evidence
    assert "uniqueTerms" in evidence
    assert "kein Beweis für identischen Duft" in evidence
    assert "Das schließt einen ähnlichen Dufteindruck nicht aus" in evidence
    assert "Händlerangebote und aktuelle Preise werden separat geprüft" in evidence
    assert "Math.random()" not in evidence


def test_real_records_offer_both_shared_and_distinct_data():
    items = json.loads(PRODUCTS.read_text(encoding="utf-8"))["products"]
    by_id = {p["product_id"]: p for p in items}
    a = by_id["SC-PDM-LAYTON-125"]
    b = by_id["SC-AL-HARAMAIN-DETOUR-NOIR-100"]
    left = set(a["fragrance_profile"]["community_accords"])
    right = set(b["fragrance_profile"]["community_accords"])
    assert len(left & right) >= 2
    assert left - right
    assert right - left
    left_notes = {note.lower() for tier in a["notes"].values() for note in tier}
    right_notes = {note.lower() for tier in b["notes"].values() for note in tier}
    assert "apple" in left_notes & right_notes


def test_missing_notes_are_not_explained_as_a_verified_mismatch():
    evidence = COMPONENT.read_text(encoding="utf-8")
    assert "Keine übereinstimmende Note in den vorhandenen Notenlisten" in evidence
    assert "Die Notenlisten können unterschiedlich vollständig sein" in evidence
    assert 'data-dufynd-comparison-evidence' in evidence
