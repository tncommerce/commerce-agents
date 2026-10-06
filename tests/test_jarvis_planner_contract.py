from pathlib import Path

MIGRATION = Path("supabase/migrations/20261006041720_jarvis_free_planner_v1.sql")


def test_planner_migration_does_not_treat_external_waits_as_global_blocker():
    sql = MIGRATION.read_text()
    assert "external_waits_are_global_blocker',false" in sql
    assert "'state','planner_gap'" in sql
    assert "'stop_reason','no_executable_work'" not in sql  # state function uses CASE, not a hardcoded lie
    assert "waiting_external tasks are parked dependencies" in sql


def test_planner_only_uses_existing_zero_spend_wake_and_records_capability_gap():
    sql = MIGRATION.read_text()
    assert "wake_dufynd_purchase_freshness()" in sql
    assert "read_dufynd_first_money_runtime()" in sql
    assert "no_autonomous_metricool_media_or_publish_readiness_handler" in sql
    assert "'paid_calls',0" in sql
    assert "'new_spend_usd',0" in sql
    assert "social.publish" not in sql
    assert "budget.spend" not in sql


def test_planner_functions_are_not_publicly_executable():
    sql = MIGRATION.read_text()
    assert (
        "revoke execute on function public.get_dufynd_next_autonomous_action() "
        "from public, anon, authenticated;" in sql
    )
    assert (
        "revoke execute on function public.plan_dufynd_free_work_v1() "
        "from public, anon, authenticated;" in sql
    )
    assert "'dufynd-free-planner-v1'" in sql
    assert "'*/2 * * * *'" in sql
