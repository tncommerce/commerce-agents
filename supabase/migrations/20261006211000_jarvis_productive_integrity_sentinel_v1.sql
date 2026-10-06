-- Jarvis V4.4: productive integrity sentinel.
-- Independent deterministic guard for release/runtime drift and business-idle failure modes.
-- No publishing, spend, outreach, credentials or commerce activation.

create or replace function public.audit_dufynd_integrity_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'public'
as $function$
declare
  q jsonb;
  fm jsonb;
  github_sha text;
  render_sha text;
  blocked_observers integer := 0;
  stalled_ready integer := 0;
  productive_handlers integer := 0;
  critical_functions_ok boolean := false;
  planner_starved boolean := false;
  issues jsonb := '[]'::jsonb;
  report jsonb;
begin
  q := public.get_dufynd_next_autonomous_action();
  fm := public.read_dufynd_first_money_runtime();

  select o.last_snapshot->>'sha'
    into github_sha
  from public.dufynd_external_observers o
  where o.observer_id='github_branch:scentai-mvp'
  limit 1;

  select o.last_snapshot->>'sha'
    into render_sha
  from public.dufynd_external_observers o
  where o.source_type='render' and o.enabled
  order by o.last_success_at desc nulls last
  limit 1;

  select count(*)::integer
    into blocked_observers
  from public.dufynd_external_observers
  where enabled and health_status='blocked_configuration';

  select count(*)::integer
    into stalled_ready
  from public.dufynd_autonomy_tasks
  where status='ready'
    and created_at < now() - interval '15 minutes';

  select count(*)::integer
    into productive_handlers
  from public.dufynd_handler_contracts
  where enabled
    and handler_id not in (
      'durability_probe',
      'supervisor_state_audit',
      'ci_pr_verifier',
      'purchase_destination_freshness_audit'
    );

  critical_functions_ok :=
    to_regprocedure('public.plan_dufynd_free_work_v1()') is not null
    and to_regprocedure('public.plan_dufynd_autonomous_business_work_v1()') is not null
    and to_regprocedure('public.reconcile_dufynd_supervisor_v2()') is not null;

  planner_starved :=
    coalesce(q->>'state','')='planner_gap'
    and coalesce((q->>'ready_count')::integer,0)=0
    and coalesce((q->>'active_count')::integer,0)=0
    and coalesce((q->>'approval_count')::integer,0)=0
    and (
      coalesce(fm->>'publication_verified','false')='false'
      or fm->>'next_evidence' is not null
    );

  if not critical_functions_ok then
    issues := issues || '"critical_runtime_function_missing"'::jsonb;
  end if;
  if github_sha is not null and render_sha is not null and github_sha is distinct from render_sha then
    issues := issues || '"github_render_sha_mismatch"'::jsonb;
  end if;
  if blocked_observers > 0 then
    issues := issues || '"blocked_observer_configuration"'::jsonb;
  end if;
  if stalled_ready > 0 then
    issues := issues || '"ready_work_not_claimed"'::jsonb;
  end if;
  if planner_starved then
    issues := issues || '"planner_starvation"'::jsonb;
  end if;
  if productive_handlers = 0 then
    issues := issues || '"no_productive_business_handler"'::jsonb;
  end if;

  report := jsonb_build_object(
    'version',1,
    'checked_at',now(),
    'status',case when jsonb_array_length(issues)=0 then 'healthy' else 'degraded' end,
    'issues',issues,
    'github_sha',github_sha,
    'render_sha',render_sha,
    'blocked_observers',blocked_observers,
    'stalled_ready',stalled_ready,
    'productive_handlers',productive_handlers,
    'planner_state',q->>'state',
    'ready_count',coalesce((q->>'ready_count')::integer,0),
    'active_count',coalesce((q->>'active_count')::integer,0),
    'planner_starved',planner_starved,
    'critical_functions_ok',critical_functions_ok,
    'owner_action_required',false,
    'new_spend_usd',0
  );

  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.integrity_v1','jarvis',report,100,now())
  on conflict(key) do update
    set value=excluded.value,
        priority=excluded.priority,
        last_verified_at=excluded.last_verified_at;

  return report;
end;
$function$;

revoke execute on function public.audit_dufynd_integrity_v1() from public, anon, authenticated;
grant execute on function public.audit_dufynd_integrity_v1() to service_role, postgres;

do $$
declare
  existing_job bigint;
begin
  select jobid into existing_job
  from cron.job
  where jobname='dufynd-integrity-sentinel-v1'
  order by jobid desc
  limit 1;

  if existing_job is not null then
    perform cron.unschedule(existing_job);
  end if;

  perform cron.schedule(
    'dufynd-integrity-sentinel-v1',
    '*/5 * * * *',
    'select public.audit_dufynd_integrity_v1();'
  );
end
$$;

select public.audit_dufynd_integrity_v1();
