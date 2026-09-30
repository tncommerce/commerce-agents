from __future__ import annotations

from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260930061000_dufynd_approval_queue_hygiene.sql"
)


def test_approval_queue_hygiene_keeps_terminal_tasks_out_of_active_gate() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "'approval_required'" in sql
    assert "t.status = 'approval_required'" in sql
    assert "t.requires_human_approval" in sql
    assert "'planned'::text, 'ready'::text, 'in_progress'::text" in sql
    assert "status = 'done'" in sql
    assert "'cancelled'::text" not in sql.split("'approval_required'", 2)[2].split(
        "'done_recent'", 1
    )[0]


def test_approval_queue_hygiene_preserves_blocked_bucket() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "'blocked'" in sql
    assert "where t.status = 'blocked'" in sql
