from pathlib import Path

SQL = Path(
    "supabase/migrations/20261006131500_jarvis_autonomous_business_planner_v1.sql"
).read_text()


def test_business_planner_creates_certified_free_work():
    assert "plan_dufynd_autonomous_business_work_v1" in SQL
    assert "'ready',120,'free'" in SQL
    assert '"kind":"supervisor_state_audit"' in SQL


def test_business_planner_preserves_owner_and_cost_fences():
    for forbidden in (
        "social.publish",
        "external.outreach",
        "gmail.send",
        "budget.spend",
        "main.merge",
        "commerce.activate",
        "credentials",
        "paid_model_call",
    ):
        assert forbidden in SQL
    assert "'paid_calls',0" in SQL
    assert "'new_spend_usd',0" in SQL


def test_uncertified_creative_recovery_is_not_fake_executable_work():
    assert "'blocked',115,'free'" in SQL
    assert '"kind":"creative_asset_recovery"' in SQL
    assert '"requires_certified_handler":true' in SQL


def test_free_planner_invokes_business_planner_after_safe_wake():
    assert "business_plan := public.plan_dufynd_autonomous_business_work_v1();" in SQL
    assert "'action','autonomous_business_planning'" in SQL
