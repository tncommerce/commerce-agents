"""Static guardrails for the reversible Thin V1 no-op migration.

A separate transactional PostgreSQL test is supplied as
tests/sql_dufynd_thin_noop_suppression.sql. Neither executes in production.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261017214500_dufynd_thin_noop_suppression.sql"
BASE = ROOT / "supabase/migrations/20261004165833_jarvis_thin_v1_free_orchestration.sql"


def test_only_synthetic_half_hour_task_is_feature_gated():
    sql = MIGRATION.read_text(encoding="utf-8")
    original = BASE.read_text(encoding="utf-8")
    needle = "-- One meaningful metadata audit per 30-minute slot, never synthetic busywork."
    assert sql.count(needle) == original.count(needle) == 1
    begin = sql.index("if coalesce((select value->>'periodic_health_tasks'='true'")
    insert = sql.index("tid:='thin-health:'")
    done = sql.index("on conflict(task_id) do nothing;", insert)
    end = sql.index("end if;", done)
    loop = sql.index("for i in 1..4 loop", done)
    assert begin < insert < done < end < loop
    # Preserve exact old synthetic insert; changing handler semantics would be a new operation.
    old_sql = original[original.index(needle): original.index("  for i in 1..4 loop", original.index(needle))]
    new_sql = sql[sql.index(needle):sql.index("  end if;", sql.index(needle))]
    assert old_sql.strip() == new_sql.strip()


def test_real_work_gates_and_rollback_present():
    sql = MIGRATION.read_text(encoding="utf-8")
    required = (
        "poll_dufynd_thin_ci()", "dufynd_thin_gate(", "prepare_dufynd_execution(",
        "checkpoint_dufynd_execution(", "finish_dufynd_execution(",
        "'purchase_destination_freshness_audit'", "periodic_health_tasks",
        "value=jsonb_set(value,'{periodic_health_tasks}','false'::jsonb,true)",
        "revoke all on function public.run_dufynd_thin_v1() from public,anon,authenticated",
        "grant execute on function public.run_dufynd_thin_v1() to service_role",
    )
    for token in required:
        assert token.lower() in sql.lower(), token
    forbidden = ("cron.unschedule", "cron.schedule(", "social.publish(", "main.merge(")
    assert all(t not in sql.lower() for t in forbidden)
