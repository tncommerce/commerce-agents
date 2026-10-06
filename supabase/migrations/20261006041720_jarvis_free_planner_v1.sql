-- Jarvis V4.1 capability-aware free planner.
-- Live-state rule: parked waiting_external rows never explain global idle by themselves.
-- Planner may only invoke existing deterministic zero-spend wakes; it cannot publish,
-- spend, message externally, mutate main, or invent arbitrary executable work.

create or replace function public.get_dufynd_next_autonomous_action()
returns jsonb
language sql
stable
set search_path to 'public'
as $function$
with next_task as (
  select to_jsonb(t) as task
  from public.dufynd_autonomy_tasks t
  where t.status='ready'
    and not t.requires_human_approval
  order by t.priority desc, t.updated_at asc, t.task_id
  limit 1
),
counts as (
  select
    count(*) filter (where status='ready' and not requires_human_approval) as ready_count,
    count(*) filter (
      where status in ('claimed','working','verifying','in_progress')
         or (
           worker_state in ('claimed','working','verifying')
           and released_at is null
           and coalesce(lease_expires_at, 'infinity'::timestamptz) > now()
         )
    ) as active_count,
    count(*) filter (where status='waiting_human_input') as waiting_human_count,
    count(*) filter (where status='waiting_external') as waiting_external_count,
    count(*) filter (
      where status='approval_required'
         or (
           requires_human_approval
           and status = any (array['planned'::text, 'ready'::text, 'in_progress'::text])
         )
    ) as approval_count
  from public.dufynd_autonomy_tasks
),
waits as (
  select
    count(distinct t.task_id) filter (
      where exists (
        select 1
        from public.dufynd_task_external_waits w
        where w.task_id=t.task_id and not w.satisfied
      )
    ) as external_with_unsatisfied_dependency,
    count(distinct t.task_id) filter (
      where not exists (
        select 1
        from public.dufynd_task_external_waits w
        where w.task_id=t.task_id and not w.satisfied
      )
    ) as external_without_verified_dependency
  from public.dufynd_autonomy_tasks t
  where t.status='waiting_external'
)
select jsonb_build_object(
  'version',4,
  'next_task',(select task from next_task),
  'ready_count',ready_count,
  'active_count',active_count,
  'waiting_human_count',waiting_human_count,
  'waiting_external_count',waiting_external_count,
  'approval_count',approval_count,
  'external_with_unsatisfied_dependency',external_with_unsatisfied_dependency,
  'external_without_verified_dependency',external_without_verified_dependency,
  'state',case
    when ready_count > 0 then 'work_available'
    when active_count > 0 then 'work_in_progress'
    when waiting_human_count > 0 or approval_count > 0 then 'owner_gate'
    else 'planner_gap'
  end,
  'stop_reason',case
    when ready_count > 0 then null
    when active_count > 0 then 'active_work'
    when waiting_human_count > 0 then 'waiting_for_human_input'
    when approval_count > 0 then 'human_approval_required'
    else 'no_executable_work'
  end,
  'external_waits_are_global_blocker',false,
  'interpretation',
    'waiting_external tasks are parked dependencies. They do not explain global idle unless runnable work is directly blocked by a verified exact dependency.'
)
from counts cross join waits;
$function$;

revoke execute on function public.get_dufynd_next_autonomous_action() from public, anon, authenticated;
grant execute on function public.get_dufynd_next_autonomous_action() to service_role, postgres;

create or replace function public.plan_dufynd_free_work_v1()
returns jsonb
language plpgsql
set search_path to 'public'
as $function$
declare
  before_state jsonb;
  after_state jsonb;
  wake_result jsonb;
  first_money jsonb;
  recommendation text;
  capability_gap text;
  report jsonb;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-free-planner-v1'));
  before_state := public.get_dufynd_next_autonomous_action();

  if before_state->>'state' in ('work_available','work_in_progress','owner_gate') then
    report := jsonb_build_object(
      'version',1,'observed_at',now(),'state',before_state->>'state',
      'action','none','reason','existing_work_or_gate_already_explains_next_step',
      'queue',before_state,'paid_calls',0,'new_spend_usd',0
    );
  else
    wake_result := public.wake_dufynd_purchase_freshness();
    after_state := public.get_dufynd_next_autonomous_action();

    if after_state->>'state'='work_available' then
      report := jsonb_build_object(
        'version',1,'observed_at',now(),'state','work_replenished',
        'action','purchase_freshness_wake','wake_result',wake_result,
        'queue',after_state,'paid_calls',0,'new_spend_usd',0
      );
    else
      first_money := public.read_dufynd_first_money_runtime();

      if coalesce((first_money->>'publication_verified')::boolean,false)=false then
        recommendation := 'social_publication_readiness';
        capability_gap := 'no_autonomous_metricool_media_or_publish_readiness_handler';
      elsif first_money->>'next_evidence'='qualified_session' then
        recommendation := 'qualified_traffic_generation';
        capability_gap := 'no_zero_spend_autonomous_traffic_generation_handler';
      elsif first_money->>'next_evidence' in ('merchant_clickout','offer_view','product_view') then
        recommendation := 'funnel_conversion_readiness';
        capability_gap := 'no_certified_conversion_experiment_handler';
      else
        recommendation := 'business_reprioritization';
        capability_gap := 'no_certified_handler_for_current_business_next_move';
      end if;

      report := jsonb_build_object(
        'version',1,'observed_at',now(),'state','planner_gap','action','none',
        'reason','no_executable_free_work_after_safe_wake','queue',after_state,
        'business_next_move',recommendation,'capability_gap',capability_gap,
        'master_action_required',false,'waiting_external_is_global_blocker',false,
        'first_money',jsonb_build_object(
          'phase',first_money->>'phase',
          'decision_state',first_money->>'decision_state',
          'next_evidence',first_money->>'next_evidence',
          'publication_verified',first_money->'publication_verified'
        ),
        'paid_calls',0,'new_spend_usd',0
      );
    end if;
  end if;

  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.planner_v1','jarvis',report,100,now())
  on conflict(key) do update
    set value=excluded.value,priority=excluded.priority,last_verified_at=excluded.last_verified_at;

  return report;
end;
$function$;

revoke execute on function public.plan_dufynd_free_work_v1() from public, anon, authenticated;
grant execute on function public.plan_dufynd_free_work_v1() to service_role, postgres;

do $$
begin
  if not exists (select 1 from cron.job where jobname='dufynd-free-planner-v1') then
    perform cron.schedule(
      'dufynd-free-planner-v1',
      '*/2 * * * *',
      'select public.plan_dufynd_free_work_v1();'
    );
  end if;
end
$$;
