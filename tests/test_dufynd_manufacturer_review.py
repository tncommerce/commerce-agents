"""Prove offline facts intake does not acquire commerce/publication authority."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from scripts import prepare_dufynd_manufacturer_review as review
from scripts.validate_dufynd_catalog_expansion_wave import validate_wave

DATA = review.ROOT / "examples/retail/data"


def inputs():
    return (
        review.INPUT.read_bytes(),
        {name: review.read_json(DATA / name) for name in review.REGISTRIES},
        review.read_json(DATA / "scentai_catalog_candidates.json"),
    )


def test_three_facts_records_with_exact_identity_and_no_public_authority():
    raw, registries, candidates = inputs()
    packet = review.prepare_review(raw, registries, candidates)
    assert len(packet["records"]) == 3
    assert packet["source_packet_sha256"] == review.digest(raw)
    assert packet["publication_authorized"] is False
    assert not {"products", "candidates", "wave_id"} & packet.keys()
    for row, original in zip(packet["records"], json.loads(raw)["candidates"], strict=True):
        facts = row["facts"]
        assert facts["notes"] == original["product_data"]["notes"]
        assert facts["proposed_product_id"] == original["product_id"]
        assert facts["gtin"] is None
        assert not any(row["gates"].values())
        assert row["facts_sha256"] == review.digest(review.canonical_bytes(facts))
        assert (
            not {"price", "in_stock", "image_url", "affiliate_url", "community", "public_path"}
            & facts.keys()
        )
    # Passing a review receipt to the old importer cannot create a staging row.
    assert validate_wave(
        packet, registries["catalog.json"], registries["scentai_catalog_staging.json"]
    ) == ["wave_has_no_candidates"]
    assert validate_wave(
        json.loads(raw), registries["catalog.json"], registries["scentai_catalog_staging.json"]
    ) == [f"candidate_{i}:merchant_1:invalid_affiliate_state" for i in (1, 2, 3)]


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "Valaya Exclusif"),
        ("concentration", "Eau de Toilette"),
        ("volume_ml", 50),
        ("product_id", "SC-OTHER-100"),
        ("identifiers", {"canonical_gtin": "1234567890123"}),
        (
            "product_data",
            {"source_url": "https://attacker.invalid", "notes": {"top": ["invented"]}},
        ),
        ("media", {"image_url": "https://attacker.invalid/image.jpg"}),
    ],
)
def test_changed_source_facts_or_rights_fail_closed(field, value):
    raw, registries, candidates = inputs()
    packet = json.loads(raw)
    packet["candidates"][0][field] = value
    with pytest.raises(ValueError, match="source_packet_drift"):
        review.prepare_review(review.canonical_bytes(packet), registries, candidates)


def test_truncated_or_duplicated_packet_rejected():
    raw, registries, candidates = inputs()
    for broken in (raw[:120], raw + b"{}"):
        with pytest.raises(ValueError, match="source_packet_drift"):
            review.prepare_review(broken, registries, candidates)
    with pytest.raises(ValueError, match="duplicate_json_key"):
        json.loads('{"x":1,"x":2}', object_pairs_hook=review.unique_json)


@pytest.mark.parametrize("registry", review.REGISTRIES)
def test_existing_id_or_same_variant_under_different_id_is_not_registered_twice(registry):
    raw, registries, candidates = inputs()
    same = deepcopy(json.loads(raw)["candidates"][2])
    registries[registry]["products"].append(same)
    with pytest.raises(ValueError, match="already_registered_or_staged"):
        review.prepare_review(raw, registries, candidates)
    same["product_id"] = "SC-ANOTHER-ID"
    same["brand"] = " PDM "
    same["concentration"] = "EDP"
    with pytest.raises(ValueError, match="already_registered_or_staged"):
        review.prepare_review(raw, registries, candidates)


def test_valaya_exclusif_stays_distinct_and_candidate_drift_is_blocked():
    raw, registries, candidates = inputs()
    assert any(
        p["product_id"] == "SC-PDM-VALAYA-EXCLUSIF-EDP-75"
        for p in registries["scentai_catalog_staging.json"]["products"]
    )
    assert len(review.prepare_review(raw, registries, candidates)["records"]) == 3
    valaya = next(p for p in candidates["products"] if p["candidate_id"] == "PDM-VALAYA-EDP")
    valaya["canonical_name"] = "Valaya Exclusif"
    with pytest.raises(ValueError, match="candidate_identity_drift"):
        review.prepare_review(raw, registries, candidates)


def test_missing_or_duplicate_registry_and_candidate_volume_rejected():
    raw, registries, candidates = inputs()
    missing = deepcopy(registries)
    del missing["catalog.json"]
    with pytest.raises(ValueError, match="missing_identity_registry"):
        review.prepare_review(raw, missing, candidates)
    duplicate = deepcopy(registries)
    duplicate["catalog.json"]["products"].append(duplicate["catalog.json"]["products"][0])
    with pytest.raises(ValueError, match="duplicate_registry_id"):
        review.prepare_review(raw, duplicate, candidates)
    candidate = next(p for p in candidates["products"] if p["candidate_id"] == "PDM-VALAYA-EDP")
    candidate["volume_ml"] = 30
    with pytest.raises(ValueError, match="candidate_volume_drift"):
        review.prepare_review(raw, registries, candidates)


def test_atomic_idempotent_private_receipt_and_conflicting_resume(tmp_path):
    payload = review.prepare_review(*inputs())
    output = tmp_path / "private" / "review.json"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: review.write_private(output, payload), range(2)))
    assert sorted(results) == ["CREATED", "UNCHANGED"]
    assert output.stat().st_mode & 0o777 == 0o600
    before = output.read_bytes()
    assert review.write_private(output, review.prepare_review(*inputs())) == "UNCHANGED"
    payload["records"][0]["facts"]["name"] = "Different"
    with pytest.raises(ValueError, match="conflicting_review_checkpoint"):
        review.write_private(output, payload)
    assert output.read_bytes() == before
    assert not list(output.parent.glob(".manufacturer-review-*"))


def test_failed_publish_leaves_no_partial_receipt_and_retry_works(tmp_path, monkeypatch):
    payload = review.prepare_review(*inputs())
    output = tmp_path / "review.json"
    original_link = os.link

    def interrupted(*args, **kwargs):
        raise OSError("simulated interruption before publish")

    monkeypatch.setattr(os, "link", interrupted)
    with pytest.raises(OSError, match="interruption"):
        review.write_private(output, payload)
    assert not output.exists()
    monkeypatch.setattr(os, "link", original_link)
    assert review.write_private(output, payload) == "CREATED"


def test_website_output_symlink_and_nonprivate_file_rejected(tmp_path):
    payload = review.prepare_review(*inputs())
    with pytest.raises(ValueError, match="outside_checkout"):
        review.write_private(
            review.ROOT / "examples/retail/storefront-web/public/review.json", payload
        )
    output = tmp_path / "review.json"
    output.symlink_to(tmp_path / "elsewhere.json")
    with pytest.raises(ValueError, match="outside_checkout"):
        review.write_private(output, payload)
    output.unlink()
    output.write_bytes(review.canonical_bytes(payload))
    output.chmod(0o644)
    with pytest.raises(ValueError, match="not_private_regular_file"):
        review.write_private(output, payload)
