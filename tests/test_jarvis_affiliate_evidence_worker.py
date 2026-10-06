from pathlib import Path

SQL = Path("supabase/migrations/20261006213000_jarvis_affiliate_evidence_worker_v1.sql").read_text()


def test_affiliate_worker_reconciles_only_verified_internal_evidence():
    assert "affiliate.evidence.top_parfuemerie.20261006" in SQL
    assert "affiliate_evidence_reconcile" in SQL
    assert "feed_ready=true" in SQL
    assert "tracking_ready=true" not in SQL
    assert "verify_tracked_product_clickout" in SQL


def test_affiliate_worker_preserves_rights_scope():
    assert "dufynd_integration_affiliate_program_context_only" in SQL
    assert "does NOT grant blanket social-ad image rights" in SQL


def test_affiliate_worker_is_zero_spend_and_no_external_action():
    for forbidden in (
        "gmail.send",
        "social.publish",
        "budget.spend",
        "main.merge",
        "commerce.activate",
        "shell.execute",
    ):
        assert forbidden in SQL
    assert "'new_spend_usd',0" in SQL


def test_free_planner_routes_affiliate_work_before_generic_business_gap():
    assert "affiliate_plan := public.plan_dufynd_affiliate_work_v1();" in SQL
    assert "'action','affiliate_evidence_planning'" in SQL


def test_affiliate_worker_is_scheduled():
    assert "dufynd-affiliate-evidence-worker-v1" in SQL
    assert "*/2 * * * *" in SQL
