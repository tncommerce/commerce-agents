"""Keep customer-facing DUFYND accord labels German and centralized."""

from pathlib import Path

LABELS = Path("examples/retail/storefront-web/lib/accordLabels.ts")
SURFACES = [
    Path("examples/retail/storefront-web/components/FragranceCatalogBrowser.tsx"),
    Path("examples/retail/storefront-web/components/FragranceComparisonPicker.tsx"),
    Path("examples/retail/storefront-web/app/vergleich/[pair]/page.tsx"),
    Path("examples/retail/storefront-web/app/duft/[slug]/page.tsx"),
]


def test_shared_accord_labels_cover_current_customer_facing_terms() -> None:
    source = LABELS.read_text(encoding="utf-8")

    expected = {
        "fresh": "Frisch",
        "citrus": "Zitrisch",
        "aquatic": "Aquatisch",
        "green": "Grün",
        "spicy": "Würzig",
        "sweet": "Süß",
        "synthetic": "Synthetisch",
        "fruity": "Fruchtig",
        "woody": "Holzig",
        "smoky": "Rauchig",
        "powdery": "Pudrig",
        "floral": "Blumig",
        "creamy": "Cremig",
        "gourmand": "Gourmand",
        "oriental": "Orientalisch",
        "aromatic": "Aromatisch",
        "leathery": "Ledrig",
        "resinous": "Harzig",
    }

    for raw, label in expected.items():
        assert f'{raw}: "{label}"' in source


def test_customer_facing_surfaces_use_shared_accord_labeler() -> None:
    for path in SURFACES:
        source = path.read_text(encoding="utf-8")
        assert 'from "@/lib/accordLabels"' in source
        assert "const ACCORD_LABELS" not in source

    comparison = SURFACES[1].read_text(encoding="utf-8")
    assert "{accordLabel(accord)}" in comparison
    assert "key={accord}" in comparison
