from pathlib import Path

SQL = Path(
    "supabase/migrations/20261008101500_jarvis_ceo_safe_cycle_v1.sql"
).read_text()


def test_ceo_cycle_plans_and_routes_existing_certified_zero_spend_work():
    assert "plan_dufynd_free_work_v1()" in SQL
    assert "dufynd_handler_contracts" in SQL
    assert "certification_status" in SQL
    assert "cost_class" in SQL
    assert "run_dufynd_content_backlog_worker_v1()" in SQL
    assert "run_dufynd_content_packet_worker_v1()" in SQL
    assert "run_dufynd_content_performance_worker_v1()" in SQL
    assert "run_dufynd_affiliate_worker_v1()" in SQL
    assert "run_dufynd_measurement_worker_v1()" in SQL


def test_ceo_cycle_fails_closed_on_external_and_owner_gate_dependencies():
    assert "q.requires_human_approval is false" in SQL
    assert "q.provider_cost_unknown is false" in SQL
    assert "q.external_review_required is false" in SQL
    assert "q.needs_freshness_recheck is false" in SQL
    assert "w.satisfied is not true" in SQL
    assert "public.dufynd_resources_conflict" in SQL
    assert "jsonb_array_elements_text(q.dependencies)" in SQL
    assert "where dep.task_id=d and dep.status='done'" in SQL


def test_ceo_cycle_does_not_fake_progress_or_enable_paid_actions():
    assert "where task_id=selected.task_id" in SQL
    assert "status='done'" in SQL
    assert "'worker_not_verified'" in SQL
    assert "'waiting_market_signal'" in SQL
    assert "'owner_gate_action_executed',false" in SQL
    assert "'paid_calls',0" in SQL
    assert "'new_spend_usd',0" in SQL
    assert "grant execute on function public.run_dufynd_ceo_safe_cycle_v1()" in SQL
    assert "to service_role, postgres" in SQL
