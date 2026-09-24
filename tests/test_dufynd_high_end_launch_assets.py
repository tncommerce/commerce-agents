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
    locked_video_count = sum(
        row["creative_state"] in locked_states for row in registry["assets"]
    )
    publish_ready_core_count = len(registry["assets"]) + int(
        carousel["status"] == "publish_ready_pending_mobile_review"
    )

    assert snapshot["high_end_final_assets_documented"] == len(registry["assets"])
    assert snapshot["high_end_creative_locked"] == locked_video_count
    assert snapshot["high_end_near_final_drafts"] == len(registry["near_final"])
    assert snapshot["high_end_rebuild_required"] == len(registry["rebuild_required"])
    assert snapshot["high_end_static_publish_ready"] == 1
    assert snapshot["effective_launch_candidates_before_mobile_review"] == publish_ready_core_count
    assert snapshot["gap_to_minimum_publish_ready_target"] == max(
        0,
        int(buffer["buffer_targets"]["minimum_publish_ready_at_launch"])
        - publish_ready_core_count,
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
    ysl = next(
        row for row in registry["assets"] if row["content_id"] == "ysl_libre_high_end_01"
    )
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
        channels = {
            row["channel"] for row in links["links"] if row["content_id"] == content_id
        }
        assert channels == {"tiktok", "instagram", "youtube"}


def test_carousel_is_rendered_for_tiktok_and_instagram_only() -> None:
    carousel = load_json(CAROUSEL)
    links = load_json(LINKS)
    social = load_json(SOCIAL_COPY)

    content_id = carousel["content_id"]
    channels = {
        row["channel"] for row in links["links"] if row["content_id"] == content_id
    }
    post = next(row for row in social["posts"] if row["content_id"] == content_id)

    assert carousel["status"] == "publish_ready_pending_mobile_review"
    assert len(carousel["rendered_assets"]) == 5
    assert channels == {"tiktok", "instagram"}
    assert set(post) == {"content_id", "tiktok", "instagram"}
    assert "Do not force" in carousel["youtube_policy"]


def test_launch_review_stops_before_publish_or_spend() -> None:
    review = load_json(REVIEW)

    assert review["state"] == "mobile_launch_buffer_review_required"
    assert review["automatic_publish_allowed"] is False
    assert review["paid_generation_authorized"] is False

    decision_ids = {row["decision_id"] for row in review["operator_decisions_required"]}
    assert decision_ids == {"mobile_launch_buffer_review", "publish_approval"}

    resolved_ids = {row["decision_id"] for row in review["resolved_operator_decisions"]}
    assert resolved_ids == {"ysl_visual_acceptance", "launch_buffer_size"}


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
    assert review["fifth_creative_rule"]["satisfied_by"] == (
        "relationship_labels_carousel_01"
    )


def test_strategy_stops_at_mobile_launch_review_gate() -> None:
    strategy = load_json(STRATEGY)

    assert strategy["active_track"] == "high_end_launch_buffer"
    assert strategy["next_action"] == "perform_mobile_launch_buffer_review"
    assert strategy["next_action_class"] == "approval_required"
    assert strategy["user_approval_required_now"] is True
    assert strategy["high_end_launch_review"] == (
        "examples/retail/data/dufynd_high_end_launch_review.json"
    )
