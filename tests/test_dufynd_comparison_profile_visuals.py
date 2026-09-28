"""Keep the free DUFYND comparison visually scannable without changing product truth."""

from pathlib import Path

PICKER = Path("examples/retail/storefront-web/components/FragranceComparisonPicker.tsx")


def test_free_comparison_has_visual_scent_dna_panel() -> None:
    source = PICKER.read_text(encoding="utf-8")

    assert "Duft-DNA auf einen Blick" in source
    assert 'aria-label="Visueller Duftprofilvergleich"' in source
    assert '<ProfileMeter label="Frische"' in source
    assert '<ProfileMeter label="Süße"' in source
    assert '<ProfileMeter label="Holzig"' in source
    assert '<ProfileMeter label="Würzig"' in source


def test_profile_meter_clamps_scores_to_visual_scale() -> None:
    source = PICKER.read_text(encoding="utf-8")

    assert "Math.max(0, Math.min(100, value * 10))" in source
    assert "Skala 0–10" in source


def test_visual_qa_opens_a_real_free_comparison() -> None:
    qa = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs").read_text(\n        encoding="utf-8"\n    )

    assert "/vergleich?left=SC-XERJOFF-NAXOS-100&right=SC-SOSPIRO-VIBRATO-100" in qa
    assert 'marker: "Duft-DNA auf einen Blick"' in qa
