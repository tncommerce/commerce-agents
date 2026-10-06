from pathlib import Path
import re

PLANNER_SQL = Path(
    "supabase/migrations/20261006131500_jarvis_autonomous_business_planner_v1.sql"
).read_text()

SENTINEL_SQL = Path(
    "supabase/migrations/20261006211000_jarvis_productive_integrity_sentinel_v1.sql"
).read_text()


def test_business_planner_creates_certified_free_work():
    assert "plan_dufynd_autonomous_business_work_v1" in PLANNER_SQL
    assert "'ready',100,'free'" in PLANNER_SQL
    assert '"kind":"supervisor_state_audit"' in PLANNER_SQL


def test_business_planner_respects_live_priority_constraint():
    priorities = [
        int(value)
        for value in re.findall(
            r"'(?:ready|blocked)',(\d+),'free'",
            PLANNER_SQL,
        )
    ]
    assert priorities
    assert min(priorities) >= 0
    assert max(priorities) <= 100


def test_business_planner_uses_canonical_resource_scopes():
    assert "social:creative-registry:read" not in PLANNER_SQL
    assert "db:dufynd.creative_registry" in PLANNER_SQL


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
        assert forbidden in PLANNER_SQL
    assert "'paid_calls',0" in PLANNER_SQL
    assert "'new_spend_usd',0" in PLANNER_SQL


def test_uncertified_creative_recovery_is_not_fake_executable_work():
    assert "'blocked',95,'free'" in PLANNER_SQL
    assert '"kind":"creative_asset_recovery"' in PLANNER_SQL
    assert '"requires_certified_handler":true' in PLANNER_SQL


def test_free_planner_invokes_business_planner_after_safe_wake():
    assert "business_plan := public.plan_dufynd_autonomous_business_work_v1();" in PLANNER_SQL
    assert "'action','autonomous_business_planning'" in PLANNER_SQL


def test_integrity_sentinel_is_independent_of_business_planner_execution():
    assert "audit_dufynd_integrity_v1" in SENTINEL_SQL
    assert "dufynd-integrity-sentinel-v1" in SENTINEL_SQL
    assert "*/5 * * * *" in SENTINEL_SQL
    assert "github_render_sha_mismatch" in SENTINEL_SQL
    assert "ready_work_not_claimed" in SENTINEL_SQL
    assert "planner_starvation" in SENTINEL_SQL
    assert "no_productive_business_handler" in SENTINEL_SQL


def test_integrity_sentinel_has_zero_spend_owner_fences():
    assert "'new_spend_usd',0" in SENTINEL_SQL
    assert "'owner_action_required',false" in SENTINEL_SQL
