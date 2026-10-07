from pathlib import Path

SQL = Path("supabase/migrations/20261007064000_jarvis_measurement_continuity_v1.sql").read_text()


def test_measurement_worker_uses_launch_attribution_not_raw_clicks():
    assert "read_dufynd_first_money_measurement_audit_v1" in SQL
    assert "occurred_at >= launch_at" in SQL
    assert "campaign_id=campaign" in SQL
    assert "content_id=content" in SQL
    assert "acquisition_source='instagram'" in SQL
    assert "'clickout_is_sale',false" in SQL


def test_measurement_worker_does_not_manufacture_traffic():
    assert "Never create traffic, click affiliate links, publish, message or spend." in SQL
    for forbidden in (
        "gmail.send",
        "social.publish",
        "budget.spend",
        "main.merge",
        "commerce.activate",
        "shell.execute",
    ):
        assert forbidden in SQL


def test_free_planner_adds_measurement_before_declaring_wait():
    assert "measurement_plan := public.plan_dufynd_measurement_work_v1();" in SQL
    assert "'action','first_money_measurement_planning'" in SQL
    assert "'state','waiting_market_signal'" in SQL
    assert "read_dufynd_safe_work_exhaustion_v1" in SQL


def test_safe_exhaustion_requires_today_business_work_done():
    for task_prefix in (
        "bizplan:zero-budget-content-queue:",
        "bizplan:content-packet:",
        "bizplan:creative-recovery:",
        "bizplan:first-money-measurement:",
    ):
        assert task_prefix in SQL
    assert "qualified_distribution_signal_required" in SQL


def test_integrity_distinguishes_waiting_market_signal_from_starvation():
    assert "safe_internal_work_exhausted" in SQL
    assert "<>'waiting_market_signal'" in SQL
    assert "planner_starvation" in SQL
    assert "run_dufynd_measurement_worker_v1" in SQL
