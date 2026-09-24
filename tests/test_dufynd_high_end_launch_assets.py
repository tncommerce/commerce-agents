from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path("examples/retail/data")
REGISTRY = DATA_DIR / "dufynd_high_end_launch_assets.json"
BUFFER = DATA_DIR / "dufynd_content_buffer_plan.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_high_end_launch_registry_is_non_publishing_and_branded() -> None:
    registry = load_json(REGISTRY)

    assert registry["system"] == "DUFYND"
    assert registry["automatic_publish_allowed"] is False
    assert "explicit_operator_publish_approval" in registry["publish_requires"]
    assert len(registry["assets"]) == 3

    payload = json.dumps(registry, ensure_ascii=False)
    assert "SCENTAI" not in payload


def test_buffer_counts_match_high_end_registry() -> None:
    registry = load_json(REGISTRY)
    buffer = load_json(BUFFER)

    snapshot = buffer["inventory_snapshot"]
    assert snapshot["high_end_final_assets_documented"] == len(registry["assets"])
    assert snapshot["high_end_creative_locked"] == sum(
        row["creative_state"] == "locked" for row in registry["assets"]
    )
    assert snapshot["high_end_near_final_drafts"] == len(registry["near_final"])
    assert snapshot["high_end_rebuild_required"] == len(registry["rebuild_required"])
    assert snapshot["gap_to_minimum_publish_ready_target"] == max(
        0,
        int(buffer["buffer_targets"]["minimum_publish_ready_at_launch"]) - len(registry["assets"]),
    )


def test_rejected_legacy_shorts_cannot_enter_launch_sequence() -> None:
    registry = load_json(REGISTRY)
    rebuild_ids = {row["content_id"] for row in registry["rebuild_required"]}
    sequence_ids = {row["content_id"] for row in registry["proposed_launch_sequence"]}

    assert rebuild_ids.isdisjoint(sequence_ids)

    for row in registry["rebuild_required"]:
        assert row["reuse_old_short"] is False
        assert row["state"] == "rebuild_from_scratch"


def test_near_final_asset_stays_conditional() -> None:
    registry = load_json(REGISTRY)
    near_final_ids = {row["content_id"] for row in registry["near_final"]}

    for row in registry["proposed_launch_sequence"]:
        if row["content_id"] in near_final_ids:
            assert row.get("condition") == "only_if_audio_and_final_qc_pass"


LINKS = DATA_DIR / "dufynd_high_end_launch_links.json"
SOCIAL_COPY = DATA_DIR / "dufynd_high_end_social_copy.json"


def test_high_end_assets_have_channel_links_and_copy() -> None:
    registry = load_json(REGISTRY)
    links = load_json(LINKS)
    social = load_json(SOCIAL_COPY)

    expected_ids = {
        row["content_id"] for row in registry["assets"] + registry["near_final"]
    }
    link_ids = {row["content_id"] for row in links["links"]}
    social_ids = {row["content_id"] for row in social["posts"]}

    assert links["link_count"] == len(expected_ids) * 3
    assert link_ids == expected_ids
    assert social_ids == expected_ids

    for content_id in expected_ids:
        channels = {
            row["channel"] for row in links["links"] if row["content_id"] == content_id
        }
        assert channels == {"tiktok", "instagram", "youtube"}
