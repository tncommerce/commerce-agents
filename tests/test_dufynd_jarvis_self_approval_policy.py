from __future__ import annotations

from pathlib import Path

from scripts.evaluate_dufynd_jarvis_self_approval import (
    evaluate_action,
    load_json,
)

POLICY_PATH = Path(
    "examples/retail/data/dufynd_jarvis_self_approval_policy_v2.json"
)


def policy() -> dict:
    return load_json(POLICY_PATH)


def complete_merge_evidence() -> dict[str, bool]:
    return {
        "control_plane_fresh": True,
        "patch_scope_valid": True,
        "required_ci_green": True,
        "tests_green": True,
        "security_checks_green": True,
        "no_unresolved_review_blocker": True,
        "non_destructive_change": True,
    }


def test_candidate_policy_is_inactive_and_fails_closed_by_default() -> None:
    payload = policy()

    assert payload["status"] == "candidate_pending_owner_activation"
    assert payload["activation"]["active"] is False

    result = evaluate_action(
        payload,
        action="read_repo_and_status",
    )

    assert result["decision"] == "owner_required"
    assert result["reason"] == "self_approval_policy_not_active"


def test_preview_allows_internal_work_without_owner_gate() -> None:
    result = evaluate_action(
        policy(),
        action="prepare_engineering_patch",
        require_active_policy=False,
    )

    assert result["decision"] == "auto_allowed"
    assert result["blockers"] == []


def test_preview_allows_ci_green_non_destructive_scentai_merge() -> None:
    result = evaluate_action(
        policy(),
        action="merge_non_destructive_change_to_scentai_mvp",
        evidence=complete_merge_evidence(),
        context={
            "target_branch": "scentai-mvp",
            "changed_paths": [
                "scripts/example.py",
                "tests/test_example.py",
            ],
        },
        require_active_policy=False,
    )

    assert result["decision"] == "auto_allowed"
    assert result["missing_evidence"] == []
    assert result["blockers"] == []


def test_merge_preview_blocks_missing_ci_evidence() -> None:
    evidence = complete_merge_evidence()
    evidence["required_ci_green"] = False

    result = evaluate_action(
        policy(),
        action="merge_non_destructive_change_to_scentai_mvp",
        evidence=evidence,
        context={"target_branch": "scentai-mvp", "changed_paths": ["scripts/example.py"]},
        require_active_policy=False,
    )

    assert result["decision"] == "blocked_missing_evidence"
    assert result["missing_evidence"] == ["required_ci_green"]


def test_merge_preview_blocks_protected_branch_and_paths() -> None:
    result = evaluate_action(
        policy(),
        action="merge_non_destructive_change_to_scentai_mvp",
        evidence=complete_merge_evidence(),
        context={
            "target_branch": "main",
            "changed_paths": [
                ".github/workflows/ci.yml",
                "supabase/migrations/20260929_test.sql",
                "requirements.txt",
            ],
        },
        require_active_policy=False,
    )

    assert result["decision"] == "blocked_missing_evidence"
    assert "target_branch_must_equal:scentai-mvp" in result["blockers"]
    assert "protected_path:.github/workflows/ci.yml" in result["blockers"]
    assert "protected_path:supabase/migrations/20260929_test.sql" in result["blockers"]
    assert "protected_file:requirements.txt" in result["blockers"]


def test_main_merge_is_explicit_owner_gate() -> None:
    result = evaluate_action(
        policy(),
        action="merge_to_main",
        require_active_policy=False,
    )

    assert result["decision"] == "owner_required"
    assert result["reason"] == "owner_gate"


def test_financial_actions_remain_owner_gated() -> None:
    for action in (
        "spend_money",
        "buy_subscription_or_credits",
        "start_or_scale_paid_advertising",
        "place_supplier_or_inventory_orders",
    ):
        result = evaluate_action(
            policy(),
            action=action,
            require_active_policy=False,
        )
        assert result["decision"] == "owner_required"


def test_unknown_action_fails_closed_to_owner() -> None:
    result = evaluate_action(
        policy(),
        action="do_something_not_in_policy",
        require_active_policy=False,
    )

    assert result["decision"] == "owner_required"
    assert result["reason"] == "unknown_action_fails_closed"


def test_prohibited_behavior_never_becomes_auto_allowed() -> None:
    result = evaluate_action(
        policy(),
        action="invent_affiliate_links",
        require_active_policy=False,
    )

    assert result["decision"] == "prohibited"


def test_product_promotion_can_self_approve_only_with_all_evidence() -> None:
    evidence = {
        "control_plane_fresh": True,
        "identity_verified": True,
        "community_qa_verified": True,
        "approved_product_image": True,
        "image_rights_verified": True,
        "fresh_current_affiliate_offer": True,
        "resolved_merchant_mapping": True,
        "search_and_recommendation_qa_passed": True,
        "no_unresolved_identity_or_version_blocker": True,
    }

    allowed = evaluate_action(
        policy(),
        action="promote_staging_product_to_live_catalog",
        evidence=evidence,
        require_active_policy=False,
    )
    assert allowed["decision"] == "auto_allowed"

    evidence["image_rights_verified"] = False
    blocked = evaluate_action(
        policy(),
        action="promote_staging_product_to_live_catalog",
        evidence=evidence,
        require_active_policy=False,
    )
    assert blocked["decision"] == "blocked_missing_evidence"
    assert blocked["missing_evidence"] == ["image_rights_verified"]


def test_organic_publish_never_substitutes_for_paid_media_approval() -> None:
    evidence = {
        "control_plane_fresh": True,
        "content_marked_ready_to_publish": True,
        "product_identity_quality_passed": True,
        "asset_rights_verified": True,
        "brand_qa_passed": True,
        "destination_link_verified": True,
        "organic_only_no_paid_spend": True,
    }

    organic = evaluate_action(
        policy(),
        action="publish_ready_organic_content",
        evidence=evidence,
        require_active_policy=False,
    )
    assert organic["decision"] == "auto_allowed"

    paid = evaluate_action(
        policy(),
        action="start_or_scale_paid_advertising",
        evidence=evidence,
        require_active_policy=False,
    )
    assert paid["decision"] == "owner_required"
