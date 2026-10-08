-- Jarvis CEO Orchestrator V1: safely plan, route and verify one certified free task.
-- Never reclassify external waits, infer evidence, bypass owner gates or create paid work.
create or replace function public.run_dufynd_ceo_safe_cycle_v1()
returns jsonb
language plpgsql
set search_path to 'public'
as $function$
declare
  plan_result jsonb;
  worker_result jsonb;
  next_state jsonb;
  selected public.dufynd_autonomy_tasks;
  task_kind text;
  current_ready integer;
  completed boolean := false;
  execution_state text := 'no_certified_work';
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-ceo-safe-cycle-v1'));

  select count(*) into current_ready
  from public.dufynd_autonomy_tasks
  where status='ready';

  -- The existing idempotent business planner may propose only allowlisted, free work.
  -- Do not generate repeated health-check tasks if useful tasks already exist.
  if current_ready=0 then
    plan_result := public.plan_dufynd_free_work_v1();
  else
    plan_result := jsonb_build_object(
      'state','work_already_queued','created_tasks','[]'::jsonb,'new_spend_usd',0
    );
  end if;

  select q.* into selected
  from public.dufynd_autonomy_tasks q
  where q.status='ready'
    and q.budget_class='free'
    and q.provider_cost_unknown is false
    and q.requires_human_approval is false
    and q.external_review_required is false
    and q.needs_freshness_recheck is false
    and q.durable_payload is not null
    and q.durable_payload->>'kind' in (
      'content_backlog_prioritize',
      'content_production_packet',
      'content_reuse_shortlist',
      'content_performance_learning',
      'first_money_measurement_diagnostic',
      'affiliate_evidence_reconcile',
      'supervisor_state_audit',
      'purchase_destination_freshness_audit'
    )
    and jsonb_typeof(q.dependencies)='array'
    and jsonb_typeof(q.resource_scope)='array'
    and public.dufynd_capability_list_valid(q.required_capabilities)
    and public.dufynd_capability_list_valid(q.forbidden_actions)
    and not exists (
      select 1
      from jsonb_array_elements_text(q.dependencies) d
      where not exists (
        select 1 from public.dufynd_autonomy_tasks dep
        where dep.task_id=d and dep.status='done'
      )
    )
    and not exists (
      select 1
      from public.dufynd_task_external_waits w
      where w.task_id=q.task_id
        and (w.satisfied is not true or w.policy<>'dependency')
    )
    and not exists (
      select 1 from public.dufynd_autonomy_tasks active
      where active.task_id<>q.task_id and active.released_at is null
        and active.lease_expires_at>now()
        and active.worker_state in ('claimed','working','verifying')
        and public.dufynd_resources_conflict(q.resource_scope,active.resource_scope)
    )
    and exists (
      select 1 from public.dufynd_handler_contracts h
      where h.handler_id=q.durable_payload->>'kind'
        and h.enabled
        and h.contract->>'cost_class'='free'
        and h.contract->>'certification_status'='certified'
    )
  order by q.priority desc,q.created_at,q.task_id
  limit 1;

  if selected.task_id is null then
    next_state := public.read_dufynd_planner_state();
    return jsonb_build_object(
      'version',1,'state',
        case when next_state->>'first_money_next_evidence'='qualified_session'
          and (next_state->>'ready_certified_free_tasks')::integer=0
          then 'waiting_market_signal' else 'no_certified_work' end,
      'stop_reason','no_eligible_safe_task',
      'plan_state',coalesce(plan_result->>'state','unknown'),
      'next_evidence',next_state->>'first_money_next_evidence',
      'ready_certified_free_tasks',next_state->'ready_certified_free_tasks',
      'waiting_external_total',next_state->'waiting_external_total',
      'owner_gate_action_executed',false,'paid_calls',0,'new_spend_usd',0,
      'completed', '[]'::jsonb
    );
  end if;

  task_kind := selected.durable_payload->>'kind';

  -- All six business workers enforce their own exact, read-only/zero-spend task contract.
  -- One worker may execute per invocation; no loop, arbitrary shell or provider call.
  case task_kind
    when 'content_backlog_prioritize' then
      worker_result := public.run_dufynd_content_backlog_worker_v1();
    when 'content_production_packet' then
      worker_result := public.run_dufynd_content_packet_worker_v1();
    when 'content_reuse_shortlist' then
      worker_result := public.run_dufynd_content_worker_v1();
    when 'content_performance_learning' then
      worker_result := public.run_dufynd_content_performance_worker_v1();
    when 'first_money_measurement_diagnostic' then
      worker_result := public.run_dufynd_measurement_worker_v1();
    when 'affiliate_evidence_reconcile' then
      worker_result := public.run_dufynd_affiliate_worker_v1();
    when 'supervisor_state_audit' then
      worker_result := public.run_dufynd_thin_v1();
    when 'purchase_destination_freshness_audit' then
      worker_result := public.run_dufynd_thin_v1();
    else
      raise exception 'unregistered safe kind';
  end case;

  if task_kind in ('supervisor_state_audit','purchase_destination_freshness_audit') then
    completed := exists (
      select 1 from jsonb_array_elements(coalesce(worker_result->'completed','[]'::jsonb)) c
      where c->>'task_id'=selected.task_id and c->>'status'='completed'
    );
  else
    completed := worker_result->>'status'='completed'
      and worker_result->>'task_id'=selected.task_id;
  end if;

  -- A worker result alone is not proof: verify the durable task state.
  if completed then
    select status='done' into completed
    from public.dufynd_autonomy_tasks where task_id=selected.task_id;
  end if;

  execution_state := case when completed then 'completed' else 'not_completed' end;
  next_state := public.read_dufynd_planner_state();

  return jsonb_build_object(
    'version',1,
    'state',execution_state,
    'stop_reason',case when completed then 'one_safe_task_completed' else 'worker_not_verified' end,
    'plan_state',coalesce(plan_result->>'state','work_already_queued'),
    'task_id',selected.task_id,
    'handler',task_kind,
    'worker_status',coalesce(worker_result->>'status',worker_result->>'stop_reason'),
    'completed',case when completed then jsonb_build_array(
      jsonb_build_object('task_id',selected.task_id,'status','completed','handler',task_kind)
    ) else '[]'::jsonb end,
    'next_evidence',next_state->>'first_money_next_evidence',
    'ready_certified_free_tasks',next_state->'ready_certified_free_tasks',
    'waiting_external_total',next_state->'waiting_external_total',
    'owner_gate_action_executed',false,'paid_calls',0,'new_spend_usd',0
  );
end;
$function$;

revoke execute on function public.run_dufynd_ceo_safe_cycle_v1()
  from public, anon, authenticated;
grant execute on function public.run_dufynd_ceo_safe_cycle_v1()
  to service_role, postgres;
