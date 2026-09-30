from pathlib import Path


MIGRATION = Path("examples/retail/data/dufynd_jarvis_v1_2_supabase_migration.sql")


def test_jarvis_v1_2_migration_allows_blocked_task_state() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "dufynd_autonomy_tasks_status_check" in sql
    assert "'blocked'::text" in sql
    assert "'waiting_external'::text" in sql
    assert "'approval_required'::text" in sql


def test_jarvis_v1_2_migration_is_explicitly_operator_gated() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "Apply only after explicit operator approval" in sql
