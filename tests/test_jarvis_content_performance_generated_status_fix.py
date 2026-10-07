from pathlib import Path

SQL = Path(
    "supabase/migrations/20261007081500_jarvis_content_performance_generated_status_fix.sql"
).read_text()


def test_generated_processing_status_is_never_written_directly():
    assert "processing_status='content_performance_learning_v1'" not in SQL
    assert "column_name='processing_status'" in SQL
    assert "is_generated" in SQL
    assert "'ALWAYS'" in SQL


def test_worker_still_completes_performance_events():
    assert "event_type='content_performance_added'" in SQL
    assert "status='done'" in SQL
    assert "processed_at=now()" in SQL
    assert "attempts=j.attempts+1" in SQL
