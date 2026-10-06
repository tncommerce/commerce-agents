-- Jarvis V4.3: bounded autonomous business planner.
-- Converts a planner gap into certified zero-spend worker tasks instead of merely reporting idle.
-- It never publishes, spends, messages externally, activates commerce, touches credentials or main.

create or replace function public.plan_dufynd_autonomous_business_work_v1()
returns jsonb
language plpgsql
set search_path to 'public'
as $function$
declare
  q jsonb;
  fm jsonb;
  move text;
  created jsonb := '[]'::jsonb;
  tid text;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-autonomous-business-planner-v1'));
  q := public.get_dufynd_next_autonomous_action();

  if q->>'state' in ('work_available','work_in_progress','owner_gate') then
    return jsonb_build_object(
      'version',1,'state',q->>'state','action','none',
      'reason','existing_work_or_gate_already_explains_next_step',
      'created_tasks',created,'paid_calls',0,'new_spend_usd',0
    );
  end if;

  fm := public.read_dufynd_first_money_runtime();

  if coalesce((fm->>'publication_verified')::boolean,false)=false then
    move := 'social_publication_readiness';

    tid := 'bizplan:social-truth:'||to_char(now() at time zone 'UTC','YYYYMMDDHH24');
    insert into public.dufynd_autonomy_tasks(
      task_id,domain,title,instruction,status,priority,budget_class,
      resource_scope,durability_policy,durable_payload,forbidden_actions
    ) values(
      tid,'supervisor','Verify social publication readiness truth',
      'Persist current First-Money publication, funnel and supervisor evidence only. Never publish or schedule content.',
      'ready',100,'free','["db:jarvis.supervisor_v2.health"]'::jsonb,'durable',
      '{"kind":"supervisor_state_audit","steps":1,"interval_seconds":2}'::jsonb,
      '["social.publish","gmail.send","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb
    ) on conflict(task_id) do nothing;
    if found then created := created || jsonb_build_array(tid); end if;

    -- Asset recovery is a planning/research task only. Until a certified read-only
    -- repository/media handler exists it remains planned, never falsely executable.
    tid := 'bizplan:creative-recovery:'||to_char(now() at time zone 'UTC','YYYYMMDD');
    insert into public.dufynd_autonomy_tasks(
      task_id,domain,title,instruction,status,priority,budget_class,
      resource_scope,durability_policy,durable_payload,forbidden_actions
    ) values(
      tid,'content','Recover and rank frozen social masters',
      'Locate persisted FROZEN >=9.5 short-form masters and produce evidence for QA. Do not generate paid media, schedule, publish or modify approved assets.',
      'blocked',95,'free','["repo:scentai-mvp:read","db:dufynd.creative_registry"]'::jsonb,'durable',
      '{"kind":"creative_asset_recovery","quality_floor":9.5,"read_only":true,"requires_certified_handler":true}'::jsonb,
      '["social.publish","gmail.send","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb
    ) on conflict(task_id) do nothing;
    if found then created := created || jsonb_build_array(tid); end if;

  elsif fm->>'next_evidence'='qualified_session' then
    move := 'qualified_traffic_generation';
    tid := 'bizplan:funnel-truth:'||to_char(now() at time zone 'UTC','YYYYMMDDHH24');
    insert into public.dufynd_autonomy_tasks(
      task_id,domain,title,instruction,status,priority,budget_class,
      resource_scope,durability_policy,durable_payload,forbidden_actions
    ) values(
      tid,'growth','Audit qualified-traffic readiness',
      'Persist bounded funnel and supervisor evidence; identify missing internal prerequisites only. Do not create traffic, publish, message or spend.',
      'ready',90,'free','["db:jarvis.supervisor_v2.health"]'::jsonb,'durable',
      '{"kind":"supervisor_state_audit","steps":1,"interval_seconds":2}'::jsonb,
      '["social.publish","gmail.send","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb
    ) on conflict(task_id) do nothing;
    if found then created := created || jsonb_build_array(tid); end if;
  else
    move := 'business_reprioritization';
  end if;

  q := public.get_dufynd_next_autonomous_action();
  return jsonb_build_object(
    'version',1,'state',case when jsonb_array_length(created)>0 then 'work_planned' else 'planner_gap' end,
    'action','bounded_business_planning','business_next_move',move,
    'created_tasks',created,'queue',q,'paid_calls',0,'new_spend_usd',0,
    'owner_action_required',false
  );
end;
$function$;

revoke execute on function public.plan_dufynd_autonomous_business_work_v1() from public, anon, authenticated;
grant execute on function public.plan_dufynd_autonomous_business_work_v1() to service_role, postgres;

create or replace function public.plan_dufynd_free_work_v1()
returns jsonb
language plpgsql
set search_path to 'public'
as $function$
declare
  before_state jsonb;
  after_state jsonb;
  wake_result jsonb;
  business_plan jsonb;
  report jsonb;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-free-planner-v1'));
  before_state := public.get_dufynd_next_autonomous_action();

  if before_state->>'state' in ('work_available','work_in_progress','owner_gate') then
    report := jsonb_build_object(
      'version',2,'observed_at',now(),'state',before_state->>'state',
      'action','none','reason','existing_work_or_gate_already_explains_next_step',
      'queue',before_state,'paid_calls',0,'new_spend_usd',0
    );
  else
    wake_result := public.wake_dufynd_purchase_freshness();
    after_state := public.get_dufynd_next_autonomous_action();

    if after_state->>'state'='work_available' then
      report := jsonb_build_object(
        'version',2,'observed_at',now(),'state','work_replenished',
        'action','purchase_freshness_wake','wake_result',wake_result,
        'queue',after_state,'paid_calls',0,'new_spend_usd',0
      );
    else
      business_plan := public.plan_dufynd_autonomous_business_work_v1();
      after_state := public.get_dufynd_next_autonomous_action();
      report := jsonb_build_object(
        'version',2,'observed_at',now(),
        'state',case when after_state->>'state'='work_available' then 'work_replenished' else coalesce(business_plan->>'state','planner_gap') end,
        'action','autonomous_business_planning','wake_result',wake_result,
        'business_plan',business_plan,'queue',after_state,
        'business_next_move',business_plan->>'business_next_move',
        'master_action_required',false,'waiting_external_is_global_blocker',false,
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
