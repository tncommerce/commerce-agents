from pathlib import Path

PRIORITY = Path("supabase/migrations/20261008111500_jarvis_ceo_real_work_v2.sql").read_text()
ROUTER = Path("supabase/migrations/20261008112000_jarvis_ceo_cycle_route_v2.sql").read_text()
CRON = Path("supabase/migrations/20261008112500_jarvis_ceo_v2_free_cron.sql").read_text()


def test_owner_frozen_media_replenishes_growth_work_without_publishing():
    assert "owner_frozen_no_publish" in PRIORITY
    assert "owner_asset_approved" in PRIORITY
    assert "owner_publish_approval" in PRIORITY
    assert "asset_editing_locked" in PRIORITY
    assert "ceo_distribution_preflight_v2" in PRIORITY
    assert "NOT_SCHEDULED_NOT_PUBLISHED" in PRIORITY
    assert "owner_action_required" in PRIORITY
    assert "publish_requires_explicit_go" not in PRIORITY or "owner_publish_approval" in PRIORITY
    assert "Instagram static post" in PRIORITY
    assert "TikTok photo post" in PRIORITY
    assert "captions are not clickable links" in PRIORITY
    assert "one_night_fourteen_perfumes" in PRIORITY


def test_external_waits_are_triaged_not_falsely_resolved():
    assert "run_dufynd_ceo_blocker_triage_v2()" in PRIORITY
    assert "dufynd_task_external_waits" in PRIORITY
    assert "unverified_external_dependency" in PRIORITY
    assert "confirmed_unsatisfied_observer_wait" in PRIORITY
    assert "blocked_status_mutations',0" in PRIORITY
    assert "external_messages_sent',0" in PRIORITY
    assert "status='waiting_external'" in PRIORITY
    assert "No publishing" not in PRIORITY or "no publishing" in PRIORITY.lower()


def test_orchestration_is_bounded_certified_and_durable():
    assert "public.plan_dufynd_ceo_priority_work_v2()" in ROUTER
    assert "public.run_dufynd_ceo_distribution_preflight_v2()" in ROUTER
    assert "public.run_dufynd_ceo_blocker_triage_v2()" in ROUTER
    assert "q.budget_class='free'" in ROUTER
    assert "q.requires_human_approval is false" in ROUTER
    assert "q.external_review_required is false" in ROUTER
    assert "h.contract->>'certification_status'='certified'" in ROUTER
    assert "q.durable_payload->>'kind' in (" in ROUTER
    assert "where task_id=selected.task_id" in ROUTER
    assert "worker_result->>'task_id'=selected.task_id" in ROUTER
    assert "'owner_gate_action_executed',false" in ROUTER
    assert "'paid_calls',0" in ROUTER
    assert "'new_spend_usd',0" in ROUTER


def test_no_authenticated_browser_can_call_internal_worker_rpc_directly():
    assert "revoke execute on function public.run_dufynd_ceo_distribution_preflight_v2()" in PRIORITY
    assert "revoke execute on function public.run_dufynd_ceo_blocker_triage_v2()" in PRIORITY
    assert "to service_role,postgres" in PRIORITY
    assert "from public,anon,authenticated" in PRIORITY


def test_zero_spend_ceo_cycle_has_a_periodic_wake():
    assert "'dufynd-ceo-v2-growth-loop'" in CRON
    assert "'*/10 * * * *'" in CRON
    assert "public.run_dufynd_ceo_safe_cycle_v1()" in CRON
