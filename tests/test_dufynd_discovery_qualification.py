import json
from copy import deepcopy
from pathlib import Path

import pytest
from scripts.build_scentai_catalog_staging import (
    attach_discovery_qualifications,
    build_staging_payload,
)

DATA = Path("examples/retail/data")


def inputs():
    staged = json.loads((DATA / "scentai_catalog_staging.json").read_text())["products"]
    for row in staged:
        row.pop("discovery", None)
    evidence = json.loads((DATA / "dufynd_discovery_qualification.json").read_text())
    return staged, evidence


def test_qualified_discovery_preserves_every_publication_and_offer_gate():
    staged, evidence = inputs()
    before = deepcopy(staged)
    attach_discovery_qualifications(staged, evidence)
    qualified = [row for row in staged if "discovery" in row]
    assert len(qualified) == len(evidence["products"])
    assert len(qualified) >= 17
    for row, old in zip(staged, before, strict=True):
        assert row["validation"] == old["validation"]
        assert row["commerce"] == old["commerce"]
        assert row["media"] == old["media"]
        if "discovery" in row:
            profile = row["discovery"]
            assert profile["publication_authorized"] is False
            assert profile["community_data_included"] is False
            assert not {"community", "rating", "price", "in_stock"} & profile.keys()
    assert build_staging_payload()["products"] == staged


@pytest.mark.parametrize(
    "field,value", [("volume_ml", 50), ("concentration", "Parfum"), ("brand", "Other")]
)
def test_mixed_variants_cannot_be_qualified(field, value):
    staged, evidence = inputs()
    evidence["products"][-1][field] = value
    with pytest.raises(ValueError, match="variant_mismatch"):
        attach_discovery_qualifications(staged, evidence)
    assert not any("discovery" in row for row in staged)


def test_gtin_checksum_and_duplicate_evidence_are_rejected():
    staged, evidence = inputs()
    gtin_row = next(row for row in evidence["products"] if row["identity"]["kind"] == "gtin")
    gtin_row["identity"]["value"] = "8411061026343"
    with pytest.raises(ValueError, match="invalid_gtin"):
        attach_discovery_qualifications(staged, evidence)
    staged, evidence = inputs()
    evidence["products"].append(deepcopy(evidence["products"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        attach_discovery_qualifications(staged, evidence)


@pytest.mark.parametrize(
    "field,value",
    [("publication_authorized", True), ("facts_only", False), ("community_data_included", True)],
)
def test_discovery_cannot_claim_publication_or_community_rights(field, value):
    staged, evidence = inputs()
    evidence["products"][0][field] = value
    with pytest.raises(ValueError, match="scope_or_evidence"):
        attach_discovery_qualifications(staged, evidence)
