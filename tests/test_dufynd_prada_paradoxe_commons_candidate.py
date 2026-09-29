import json
from pathlib import Path

EVIDENCE = Path("examples/retail/data/dufynd_prada_paradoxe_commons_image_candidate_20260929.json")


def load() -> dict:
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def test_prada_commons_candidate_has_reusable_rights_but_stays_pending() -> None:
    payload = load()
    product = payload["product"]
    candidate = payload["candidate"]
    license_data = candidate["license"]

    assert payload["status"] == "pending_review"
    assert product["product_id"] == "SC-PRADA-PARADOXE-EDP-90"
    assert product["target_volume_ml"] == 90
    assert product["target_gtin"] == "3614273760164"

    assert candidate["source_provider"] == "Wikimedia Commons"
    assert candidate["author"] == "Jacek Halicki"
    assert license_data["name"] == "CC BY-SA 4.0"
    assert license_data["commercial_reuse_permitted_by_license"] is True
    assert license_data["attribution_required"] is True
    assert license_data["share_alike_required"] is True
    assert candidate["rights_status"] == "verified_licensed_source"

    assert candidate["fidelity_status"] == "pending_exact_variant_verification"
    assert candidate["exact_variant_verified"] is False
    assert candidate["approval_status"] == "pending_review"
    assert candidate["public_catalog_use_allowed_now"] is False
    assert payload["user_approval_required_for_final_image"] is True


def test_prada_commons_candidate_does_not_infer_exact_size_from_product_family() -> None:
    payload = load()
    candidate = payload["candidate"]

    assert candidate["source_page_url"].startswith("https://commons.wikimedia.org/")
    assert candidate["asset_url"].startswith("https://upload.wikimedia.org/")
    assert candidate["license"]["url"] == "https://creativecommons.org/licenses/by-sa/4.0/"
    assert "do_not_infer_90_ml_from_bottle_shape" in payload["prohibited_automatic_actions"]
    assert "90 ml" in payload["evidence"]["blocking_reason"]
