from pathlib import Path

SQL = Path("supabase/migrations/20261006213500_jarvis_zero_budget_content_queue_v1.sql").read_text()


def test_current_zero_budget_policy_is_persisted():
    assert "content.zero_budget_policy.20261006" in SQL
    assert "zero_budget_until_2026_12_01" in SQL
    assert "same_person_different_scent" in SQL
    assert "split_screen_before_after" in SQL
    assert "tinyfish_requires_owner_go_each_use" in SQL


def test_backlog_worker_prioritizes_without_generating():
    assert "read_dufynd_zero_budget_content_queue_v1" in SQL
    assert "run_dufynd_content_backlog_worker_v1" in SQL
    assert "'publishing_allowed',false" in SQL
    assert "'new_spend_usd',0" in SQL


def test_hard_gate_concepts_are_paused():
    assert "idea_persona_shift_001" in SQL
    assert "idea_season_switch_001" in SQL
    assert "conflicts_with_current_owner_creative_gate" in SQL


def test_expensive_generation_concepts_are_held():
    assert "idea_fragrance_genesis_001" in SQL
    assert "idea_adrenaline_reveal_001" in SQL
    assert "hold_paid_generation" in SQL


def test_free_planner_routes_daily_zero_budget_queue():
    assert "content_plan := public.plan_dufynd_zero_budget_content_work_v1();" in SQL
    assert "'action','zero_budget_content_planning'" in SQL
    assert "dufynd-content-backlog-worker-v1" in SQL
