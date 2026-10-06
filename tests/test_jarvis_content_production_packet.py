from pathlib import Path

SQL = Path("supabase/migrations/20261006215000_jarvis_content_production_packet_v1.sql").read_text()


def test_content_packet_uses_ranked_zero_budget_candidate():
    assert "jarvis.zero_budget_content_queue_v1" in SQL
    assert "read_dufynd_content_production_packet_v1" in SQL
    assert "content_production_packet" in SQL


def test_packet_contains_real_production_guidance_and_qa():
    for field in (
        "visual_direction",
        "copy_structure",
        "scroll_stop_question",
        "fresh_visual_recheck_required",
        "create_or_select_visual_then_run_fresh_creative_qa",
    ):
        assert field in SQL
    assert "'target_score',9.5" in SQL


def test_packet_cannot_publish_or_spend():
    assert "'paid_generation_allowed',false" in SQL
    assert "'publishing_allowed',false" in SQL
    for forbidden in (
        "gmail.send",
        "social.publish",
        "budget.spend",
        "main.merge",
        "commerce.activate",
        "shell.execute",
    ):
        assert forbidden in SQL


def test_free_planner_routes_packet_after_daily_queue():
    assert "packet_plan := public.plan_dufynd_content_packet_work_v1();" in SQL
    assert "'action','content_packet_planning'" in SQL
    assert "dufynd-content-packet-worker-v1" in SQL
