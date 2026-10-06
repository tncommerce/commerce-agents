from pathlib import Path

SQL = Path("supabase/migrations/20261006212500_jarvis_content_reuse_worker_v1.sql").read_text()


def test_content_worker_is_productive_and_zero_spend():
    assert "run_dufynd_content_worker_v1" in SQL
    assert "read_dufynd_content_reuse_audit_v1" in SQL
    assert "'content_reuse_shortlist'" in SQL
    assert "'new_spend_usd',0" in SQL
    assert "dufynd_content_assets" in SQL


def test_content_worker_never_publishes_or_generates():
    for forbidden in (
        "social.publish",
        "gmail.send",
        "budget.spend",
        "main.merge",
        "commerce.activate",
        "shell.execute",
    ):
        assert forbidden in SQL
    assert "Do not generate, schedule, publish, message" in SQL


def test_content_worker_requires_current_visual_recheck():
    assert "'current_quality_floor',9.5" in SQL
    assert "'requires_current_visual_recheck',true" in SQL
    assert "legacy_quality_pass_recheck_required" in SQL


def test_planner_creates_executable_content_work():
    assert "'content','Build zero-spend content reuse shortlist'" in SQL
    assert "'ready',95,'free'" in SQL
    assert '{"kind":"content_reuse_shortlist","version":1}' in SQL
    assert "'blocked',95,'free'" not in SQL


def test_content_worker_is_scheduled_but_bounded():
    assert "dufynd-content-reuse-worker-v1" in SQL
    assert "*/2 * * * *" in SQL
    assert "limit 1" in SQL.lower()
