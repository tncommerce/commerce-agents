-- Read-only evidence for the free counted preflight; no reconciliation or reservation mutation.
create function public.get_dufynd_counted_preflight_state()
returns jsonb language sql stable security invoker set search_path=public as $$
select jsonb_build_object(
  'provider_contract',(select to_jsonb(c) from public.dufynd_provider_contracts c
    where contract_id='anthropic-sonnet5-counted-margin-v1'),
  'functions',(select coalesce(jsonb_agg(p.proname order by p.proname),'[]'::jsonb)
    from pg_proc p join pg_namespace n on n.oid=p.pronamespace
    where n.nspname='public' and p.proname in (
      'resolve_dufynd_nightshift_budget','reserve_dufynd_model_call',
      'dispatch_dufynd_counted_call','settle_dufynd_counted_call',
      'reconcile_dufynd_budget_reservations')),
  'leases',jsonb_build_object(
    'active_workers',(select coalesce(jsonb_agg(jsonb_build_object(
      'task_id',task_id,'worker_owner',worker_owner,'resource_scope',resource_scope,
      'lease_expires_at',lease_expires_at)),'[]'::jsonb) from public.dufynd_autonomy_tasks
      where lease_expires_at>now() and released_at is null),
    'tech',(select jsonb_build_object('status',value->>'status','expires_at',value->>'expires_at')
      from public.dufynd_master_status where key='continuity.tech_lease')),
  'observer_health',(select coalesce(jsonb_agg(jsonb_build_object(
    'observer_id',observer_id,'source_type',source_type,'health_status',health_status,
    'last_success_at',last_success_at,'consecutive_failures',consecutive_failures,
    'interval_seconds',interval_seconds,
    'stale',last_success_at is null or last_success_at<now()-make_interval(secs=>interval_seconds*2))
    order by observer_id),'[]'::jsonb) from public.dufynd_external_observers where enabled),
  'historical_pilot_budget',public.get_dufynd_jarvis_budget_status('jarvis_activation_pilot_001'),
  'reservation_snapshot',jsonb_build_object(
    'existing_total',(select count(*) from public.dufynd_budget_reservations),
    'existing_dispatched',(select count(*) from public.dufynd_budget_reservations where status='dispatched'))
);
$$;
revoke all on function public.get_dufynd_counted_preflight_state() from public,anon,authenticated;
grant execute on function public.get_dufynd_counted_preflight_state() to service_role;
