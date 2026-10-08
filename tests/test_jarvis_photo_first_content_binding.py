from pathlib import Path

SQL = Path(
    "supabase/migrations/20261008050000_jarvis_photo_first_content_binding_fix.sql"
).read_text()


def test_owner_photo_first_lifestyle_concepts_can_enter_now_lane():
    assert "i.format_id='lifestyle_product_placement'" in SQL
    assert "coalesce(i.source,'') like 'owner_%'" in SQL
    assert "then 'now'" in SQL
    assert "then 35" in SQL


def test_packet_worker_binds_output_to_claimed_task_idea():
    assert "task_idea_id := t.durable_payload->>'idea_id'" in SQL
    assert "read_dufynd_content_production_packet_for_idea_v1(task_idea_id)" in SQL
    assert "packet->>'idea_id' is distinct from task_idea_id" in SQL


def test_rejected_ideas_are_not_packetized():
    assert "i.status='planned'" in SQL
    assert "'task_idea_not_planned'" in SQL


def test_photo_first_packet_has_visual_story_reject_gate():
    assert "photo_first_single_scene" in SQL
    assert "story_readable_from_body_language_before_copy" in SQL
    assert "reject_if_story_requires_long_reading" in SQL
    assert "'target_score',9.5" in SQL


def test_fix_remains_zero_spend_and_non_publishing():
    assert "'paid_generation_allowed',false" in SQL
    assert "'publishing_allowed',false" in SQL
    assert "'new_spend_usd',0" in SQL
