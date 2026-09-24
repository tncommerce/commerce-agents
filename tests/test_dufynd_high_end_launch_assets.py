from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path("examples/retail/data")
REGISTRY = DATA_DIR / "dufynd_high_end_launch_assets.json"
BUFFER = DATA_DIR / "dufynd_content_buffer_plan.json"
REVIEW = DATA_DIR / "dufynd_high_end_launch_review.json"
STRATEGY = DATA_DIR / "dufynd_content_strategy.json"
CAROUSEL = DATA_DIR / "dufynd_launch_carousel_01.json"
LINKS = DATA_DIR / "dufynd_high_end_launch_links.json"
SOCIAL_COPY = DATA_DIR / "dufynd_high_end_social_copy.json"
CHECKLIST = DATA_DIR / "dufynd_high_end_pre_publish_checklist.json"
PROFILE_LINKS = DATA_DIR / "dufynd_social_profile_links.json"
RUNBOOK = DATA_DIR / "dufynd_launch_day_runbook.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_high_end_launch_registry_is_non_publishing_and_branded() -> None:
    registry = load_json(REGISTRY)

    assert registry["system"] == "DUFYND"
    assert registry["automatic_publish_allowed"] is False
    assert "explicit_operator_publish_approval" in registry["publish_requires"]
    assert len(registry["assets"]) == 4

    payload = json.dumps(registry, ensure_ascii=False)
    assert "SCENTAI" not in payload


def test_buffer_counts_match_five_creative_inventory() -> None:
    registry = load_json(REGISTRY)
    buffer = load_json(BUFFER)
    carousel = load_json(CAROUSEL)

    snapshot = buffer["inventory_snapshot"]
    locked_states = {
        "locked",
        "locked_visual_native_audio_at_publish",
    }
    locked_video_count = sum(row["creative_state"] in locked_states for row in registry["assets"])
    publish_ready_core_count = len(registry["assets"]) + int(
        carousel["status"]
        in {"publish_ready_pending_mobile_review", "accepted_launch_education_slot"}
    )

    assert snapshot["high_end_final_assets_documented"] == len(registry["assets"])
    assert snapshot["high_end_creative_locked"] == locked_video_count
    assert snapshot["high_end_near_final_drafts"] == len(registry["near_final"])
    assert snapshot["high_end_rebuild_required"] == len(registry["rebuild_required"])
    assert snapshot["high_end_static_publish_ready"] == 1
    assert snapshot["effective_launch_candidates_before_mobile_review"] == publish_ready_core_count
    assert snapshot["gap_to_minimum_publish_ready_target"] == max(
        0,
        int(buffer["buffer_targets"]["minimum_publish_ready_at_launch"]) - publish_ready_core_count,
    )


def test_rejected_legacy_shorts_cannot_enter_launch_sequence() -> None:
    registry = load_json(REGISTRY)
    rebuild_ids = {row["content_id"] for row in registry["rebuild_required"]}
    sequence_ids = {row["content_id"] for row in registry["proposed_launch_sequence"]}

    assert rebuild_ids.isdisjoint(sequence_ids)

    for row in registry["rebuild_required"]:
        assert row["reuse_old_short"] is False
        assert row["state"] == "rebuild_from_scratch"


def test_ysl_libre_visual_is_locked_with_native_audio_rule() -> None:
    registry = load_json(REGISTRY)
    ysl = next(row for row in registry["assets"] if row["content_id"] == "ysl_libre_high_end_01")
    sequence = next(
        row
        for row in registry["proposed_launch_sequence"]
        if row["content_id"] == "ysl_libre_high_end_01"
    )

    assert ysl["creative_state"] == "locked_visual_native_audio_at_publish"
    assert "approved the visual at 9/10" in ysl["note"]
    assert "Do not regenerate" in ysl["note"]
    assert sequence["publish_audio_rule"] == (
        "add_current_platform_native_or_trending_audio_at_publish"
    )


def test_video_assets_have_three_channel_links_and_copy() -> None:
    registry = load_json(REGISTRY)
    links = load_json(LINKS)
    social = load_json(SOCIAL_COPY)

    video_ids = {row["content_id"] for row in registry["assets"]}
    link_ids = {row["content_id"] for row in links["links"]}
    social_ids = {row["content_id"] for row in social["posts"]}

    assert video_ids.issubset(link_ids)
    assert video_ids.issubset(social_ids)

    for content_id in video_ids:
        channels = {row["channel"] for row in links["links"] if row["content_id"] == content_id}
        assert channels == {"tiktok", "instagram", "youtube"}


def test_carousel_is_rendered_for_tiktok_and_instagram_only() -> None:
    carousel = load_json(CAROUSEL)
    links = load_json(LINKS)
    social = load_json(SOCIAL_COPY)

    content_id = carousel["content_id"]
    channels = {row["channel"] for row in links["links"] if row["content_id"] == content_id}
    post = next(row for row in social["posts"] if row["content_id"] == content_id)

    assert carousel["status"] == "accepted_launch_education_slot"
    assert carousel["operator_review"]["state"] == "accepted_no_rework"
    assert len(carousel["rendered_assets"]) == 5
    assert channels == {"tiktok", "instagram"}
    assert set(post) == {"content_id", "tiktok", "instagram"}
    assert "Do not force" in carousel["youtube_policy"]


def test_launch_review_stops_before_publish_or_spend() -> None:
    review = load_json(REVIEW)

    assert review["state"] == "mobile_launch_buffer_review_passed_publish_gate_pending"
    assert review["automatic_publish_allowed"] is False
    assert review["paid_generation_authorized"] is False

    decision_ids = {row["decision_id"] for row in review["operator_decisions_required"]}
    assert decision_ids == {"publish_approval"}

    resolved_ids = {row["decision_id"] for row in review["resolved_operator_decisions"]}
    assert resolved_ids == {
        "ysl_visual_acceptance",
        "launch_buffer_size",
        "mobile_launch_buffer_review",
        "relationship_labels_carousel_acceptance",
        "one_million_topaz_final_qc",
    }


def test_launch_review_records_full_minimum_buffer() -> None:
    review = load_json(REVIEW)
    buffer = load_json(BUFFER)

    assert review["quality_floor"] == "Naxos-level premium visual quality"
    assert review["readiness_summary"]["locked_final_video_masters"] == 4
    assert review["readiness_summary"]["rendered_static_creatives"] == 1
    assert review["readiness_summary"]["publish_ready_core_creatives_before_mobile_review"] == 5
    assert review["readiness_summary"]["minimum_launch_buffer_target"] == 5
    assert review["readiness_summary"]["gap_to_minimum"] == 0
    assert buffer["inventory_snapshot"]["gap_to_minimum_publish_ready_target"] == 0

    excluded = {row["content_id"] for row in review["rebuild_exclusions"]}
    assert excluded == {"sillage_haltbarkeit_01", "edp_vs_edt_01"}
    assert review["fifth_creative_rule"]["satisfied_by"] == ("relationship_labels_carousel_01")


def test_strategy_advances_to_pre_publish_gate() -> None:
    strategy = load_json(STRATEGY)

    assert strategy["active_track"] == "high_end_launch_buffer"
    assert strategy["next_action"] == (
        "launch_day_rebrand_and_live_checks_then_request_publish_approval"
    )
    assert strategy["next_action_class"] == "manual_step_pending_at_launch"
    assert strategy["user_approval_required_now"] is False
    assert strategy["high_end_launch_review"] == (
        "examples/retail/data/dufynd_high_end_launch_review.json"
    )


def test_mobile_review_records_five_publish_ready_creatives() -> None:
    review = load_json(REVIEW)
    buffer = load_json(BUFFER)

    assert review["readiness_summary"]["publish_ready_core_creatives_after_mobile_review"] == 5
    assert review["readiness_summary"]["mobile_review_passed"] is True
    assert buffer["inventory_snapshot"]["publish_ready_core_creatives_after_mobile_review"] == 5
    assert buffer["inventory_snapshot"]["high_end_final_assets_pending_mobile_review"] == 0
    assert buffer["inventory_snapshot"]["mobile_launch_buffer_review"] == "passed"


def test_pre_publish_checklist_covers_five_core_slots() -> None:
    checklist = load_json(CHECKLIST)

    assert checklist["state"] == "prelaunch_ready_waiting_launch_day_live_checks"
    assert checklist["automatic_publish_allowed"] is False
    assert checklist["paid_generation_required"] is False
    assert checklist["tracking_qc"]["status"] == "passed_code_level"
    assert checklist["tracking_qc"]["link_count"] == 14
    assert len(checklist["launch_slots"]) == 5
    assert checklist["final_gate"]["required"] == "explicit_operator_publish_approval"

    ids = {row["content_id"] for row in checklist["launch_slots"]}
    assert ids == {
        "naxos_high_end_01",
        "bois_imperial_high_end_01",
        "one_million_example61_01",
        "ysl_libre_high_end_01",
        "relationship_labels_carousel_01",
    }


def test_pre_publish_checklist_keeps_rejected_legacy_shorts_out() -> None:
    checklist = load_json(CHECKLIST)

    excluded = {row["content_id"] for row in checklist["rebuild_exclusions"]}
    slot_ids = {row["content_id"] for row in checklist["launch_slots"]}

    assert excluded == {"sillage_haltbarkeit_01", "edp_vs_edt_01"}
    assert excluded.isdisjoint(slot_ids)


def test_social_profile_links_are_stable_and_channel_specific() -> None:
    profile_links = load_json(PROFILE_LINKS)

    assert profile_links["landing_path"] == "/start"
    assert len(profile_links["links"]) == 3
    channels = {row["channel"] for row in profile_links["links"]}
    assert channels == {"tiktok", "instagram", "youtube"}

    for row in profile_links["links"]:
        assert row["url"].startswith("https://dufynd.de/start?")
        assert f"src={row['channel']}" in row["url"]
        assert "content=profile" in row["url"]


def test_launch_day_runbook_preserves_publish_gate_and_five_slots() -> None:
    runbook = load_json(RUNBOOK)

    assert runbook["state"] == "prelaunch_ready_waiting_launch_day_live_checks"
    assert runbook["automatic_publish_allowed"] is False
    assert len(runbook["benchmark_schedule"]) == 5
    assert runbook["benchmark_schedule"][0]["content_id"] == "naxos_high_end_01"
    assert "No social publish without explicit operator approval." in runbook["hard_stops"]


def test_social_copy_has_profile_link_cta_for_every_channel() -> None:
    social = load_json(SOCIAL_COPY)

    for post in social["posts"]:
        assert post["tiktok"]["cta"].endswith("Link im Profil.")
        assert post["instagram"]["cta"].endswith("Link im Profil.")
        if "youtube" in post:
            assert post["youtube"]["cta"] == "DUFYND über den Link im Kanalprofil öffnen."
