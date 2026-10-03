import json
from copy import deepcopy
from pathlib import Path

import pytest
from scripts.build_scentai_campaign_link import build_campaign_url
from scripts.check_dufynd_content_review import CHECKS, evaluate, revision_hash


def reviewed():
    package = {
        "maker_id": "maker-A",
        "content_id": "creative-1",
        "campaign_id": "campaign-1",
        "platform": "youtube",
        "product_id": "product-1",
        "assets": [{"uri": "internal://frozen-master", "sha256": "a" * 64}],
        "caption": "Exact variant, transparent affiliate disclosure",
        "affiliate_destination": "https://example.org/approved-offer",
    }
    return {
        "package": package,
        "revision_round": 0,
        "review": {
            "checker_id": "checker-B",
            "revision_hash": revision_hash(package),
            "hard_fails": [],
            "checks": {
                name: {"result": "PASS", "evidence_ref": f"internal://review/{name}"}
                for name in CHECKS
            },
        },
    }


def test_independent_evidenced_review_only_reaches_owner_gate():
    result = evaluate(reviewed())
    assert result["stage"] == "READY_FOR_OWNER_APPROVAL"
    assert result["publication_authorized"] is False
    assert result["authority"] == "OFFLINE_CONTRACT_ONLY"


def test_self_approval_cannot_be_bypassed_by_owner_flag_or_score():
    doc = reviewed()
    doc["review"].update(checker_id="  MAKER-a ", score=100)
    doc["owner_approval"] = True
    assert "self_approval_forbidden" in evaluate(doc)["reasons"]


@pytest.mark.parametrize("name", CHECKS)
def test_each_mandatory_check_blocks_even_with_perfect_average(name):
    doc = reviewed()
    doc["review"]["checks"][name]["result"] = "FAIL"
    doc["review"]["average_score"] = 100
    assert f"check_not_evidenced:{name}" in evaluate(doc)["reasons"]


@pytest.mark.parametrize("field", ["caption", "product_id", "affiliate_destination"])
def test_changed_package_requires_fresh_independent_review(field):
    doc = reviewed()
    doc["package"][field] = "changed"
    assert "review_revision_mismatch" in evaluate(doc)["reasons"]


def test_changed_asset_or_missing_digest_invalidates_review():
    doc = reviewed()
    doc["package"]["assets"][0]["sha256"] = "b" * 64
    assert "review_revision_mismatch" in evaluate(doc)["reasons"]
    doc["package"]["assets"][0]["sha256"] = None
    assert "frozen_asset_digests_required" in evaluate(doc)["reasons"]


def test_revision_requires_full_new_review_and_is_bounded():
    doc = reviewed()
    doc["review"]["hard_fails"] = ["wrong_bottle"]
    assert evaluate(doc)["stage"] == "REVISION_REQUIRED"
    revised = deepcopy(doc)
    revised["package"]["assets"][0]["sha256"] = "b" * 64
    revised["revision_round"] = 1
    revised["review"]["hard_fails"] = []
    assert "review_revision_mismatch" in evaluate(revised)["reasons"]
    revised["review"]["revision_hash"] = revision_hash(revised["package"])
    assert evaluate(revised)["stage"] == "READY_FOR_OWNER_APPROVAL"
    revised["revision_round"] = 3
    assert "revision_limit_owner_exception_required" in evaluate(revised)["reasons"]


def test_unknown_or_evidence_free_checks_fail_closed():
    doc = reviewed()
    doc["review"]["checks"]["asset_rights"]["evidence_ref"] = None
    del doc["review"]["checks"]["audio_rights"]
    doc["review"]["hard_fails"] = None
    assert len(evaluate(doc)["reasons"]) == 3
    assert evaluate({})["stage"] == "REVISION_REQUIRED"


def test_first_loop_links_preserve_creative_and_separate_landing_test():
    path = Path(__file__).resolve().parents[1] / "docs/supervisor/dufynd-first-revenue-loop.json"
    manifest = json.loads(path.read_text())
    for post in manifest["platforms"]:
        expected = build_campaign_url(
            base_url="https://dufynd.de",
            landing_path="/duft/rabanne-1-million",
            channel=post["platform"],
            campaign_id=manifest["experiment"]["candidate_campaign"],
            content_id=manifest["content_id"],
        )
        assert post["proposed_product_url"] == expected
        assert post["platform_content_id"] is None
        assert post["published_link_verified"] is False
    assert all(value is None for value in manifest["revenue"].values())
    assert manifest["experiment"]["publication_authorized"] is False
