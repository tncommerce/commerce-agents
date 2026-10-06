from pathlib import Path

SQL = Path(
    "supabase/migrations/20261006215500_jarvis_private_observer_integrity_v2.sql"
).read_text()


def test_sentinel_detects_stale_private_observers_even_before_health_projection():
    assert "stale_private_observers" in SQL
    assert "last_success_at < now()-interval '20 minutes'" in SQL
    assert "next_retry_at < now()-interval '15 minutes'" in SQL
    assert "private_observer_stale" in SQL
    assert "gmail_observer_stale" in SQL
    assert "render_observer_stale" in SQL


def test_sentinel_detects_private_broker_scheduler_gap():
    assert "dufynd_broker_acceptance_sessions" in SQL
    assert "last_private_broker_capture_at" in SQL
    assert "private_broker_scheduler_gap" in SQL
    assert "expected_private_broker_schedule_minutes" in SQL
    assert "interval '25 minutes'" in SQL


def test_sentinel_requires_productive_runtime_functions():
    for function in (
        "run_dufynd_content_worker_v1",
        "run_dufynd_affiliate_worker_v1",
        "run_dufynd_content_backlog_worker_v1",
        "run_dufynd_content_packet_worker_v1",
    ):
        assert function in SQL


def test_integrity_detection_is_zero_spend_and_non_mutating_external_state():
    assert "'new_spend_usd',0" in SQL
    assert "social.publish" not in SQL
    assert "gmail.send" not in SQL
    assert "commerce.activate" not in SQL
