"""Keep Batch 7 identifier observations isolated from canonical product truth."""

import json
from pathlib import Path

DOSSIER = Path("examples/retail/data/dufynd_batch7_identifier_evidence_20260928.json")


def load_dossier() -> dict:
    return json.loads(DOSSIER.read_text(encoding="utf-8"))


def test_identifier_dossier_is_research_only() -> None:
    dossier = load_dossier()

    assert dossier["scope"] == "research_only_not_builder_input"
    assert dossier["policy"]["canonical_gtin_assignment"].startswith("forbidden")
    assert dossier["policy"]["staging_mutation"] == "not_performed"
    assert dossier["policy"]["live_catalog_mutation"] == "not_performed"
    assert dossier["policy"]["publication"] == "blocked"


def test_identifier_dossier_never_canonicalizes_observations() -> None:
    products = {row["product_id"]: row for row in load_dossier()["products"]}

    alien = products["SC-MUGLER-ALIEN-EDP-90"]
    assert alien["canonical_gtin"] is None
    assert {row["gtin"] for row in alien["observations"]} == {"3439602802113"}

    afnan = products["SC-AFNAN-9-PM-POUR-FEMME-EDP-100"]
    assert afnan["canonical_gtin"] is None
    assert {row["gtin"] for row in afnan["observations"]} == {
        "6290171072607",
        "6290178899719",
    }

    jadore = products["SC-DIOR-JADORE-EDP-100"]
    assert jadore["canonical_gtin"] is None
    assert {row["gtin"] for row in jadore["observations"]} == {
        "3348900417878",
        "3348901738224",
    }
