-- Jarvis V5.0: First-Money measurement continuity.
-- Adds a deterministic zero-spend measurement worker and distinguishes true
-- planner starvation from a legitimate wait for qualified external traffic.

create or replace function public.read_dufynd_first_money_measurement_audit_v1()
returns jsonb
language plpgsql
stable
set search_path to 'public'
as $function$
declare
  fm jsonb;
  campaign text;
  content text;
  launch_at timestamptz;
  prelaunch_events integer := 0;
  post_landing integer := 0;
  post_product integer := 0;
  post_offer integer := 0;
  post_clickout integer := 0;
  organic_clickouts integer := 0;
  instrumentation_proven boolean := false;
  decision text;
  next_move text;
begin
  fm := public.read_dufynd_first_money_runtime();
  campaign := fm->>'experiment_id';
  content := fm->>'content_id';
  launch_at := nullif(fm#>>'{schedule,instagram}','')::timestamptz;

  if launch_at is not null then
    select count(*)::integer
      into prelaunch_events
    from public.scentai_analytics_events
    where occurred_at < launch_at
      and campaign_id=campaign
      and content_id=content
      and acquisition_source='instagram'
      and event in ('page_view','fragrance_detail_view','offer_section_view','merchant_clickout');

    select count(*)::integer
      into post_landing
    from public.scentai_analytics_events
    where occurred_at >= launch_at
      and campaign_id=campaign
      and content_id=content
      and acquisition_source='instagram'
      and event='page_view'
      and surface='acquisition_landing';

    select count(*)::integer
      into post_product
    from public.scentai_analytics_events
    where occurred_at >= launch_at
      and campaign_id=campaign
      and content_id=content
      and acquisition_source='instagram'
      and event='fragrance_detail_view';

    select count(*)::integer
      into post_offer
    from public.scentai_analytics_events
    where occurred_at >= launch_at
      and campaign_id=campaign
      and content_id=content
      and acquisition_source='instagram'
      and event='offer_section_view';

    select count(*)::integer
      into post_clickout
    from public.scentai_analytics_events
    where occurred_at >= launch_at
      and campaign_id=campaign
      and content_id=content
      and acquisition_source='instagram'
      and event='merchant_clickout';

    select count(*)::integer
      into organic_clickouts
    from public.scentai_analytics_events
    where occurred_at >= launch_at
      and event='merchant_clickout'
      and campaign_id is null
      and content_id is null;
  end if;

  instrumentation_proven := prelaunch_events > 0;

  if launch_at is null then
    decision := 'publication_schedule_missing';
    next_move := 'verify_publication_schedule_truth';
  elsif post_clickout > 0 then
    decision := 'attributed_clickout_signal_present';
    next_move := 'verify_network_transaction_evidence_without_treating_clickout_as_sale';
  elsif post_landing > 0 then
    decision := 'qualified_traffic_present_no_clickout';
    next_move := 'optimize_offer_transition_and_clickout_conversion';
  elsif instrumentation_proven then
    decision := 'waiting_for_qualified_distribution_signal';
    next_move := 'produce_and_publish_owner_approved_reach_content_then_measure_again';
  else
    decision := 'measurement_instrumentation_unproven';
    next_move := 'repair_or_verify_campaign_attribution_instrumentation';
  end if;

  return jsonb_build_object(
    'version',1,
    'observed_at',now(),
    'experiment_id',campaign,
    'content_id',content,
    'launch_at',launch_at,
    'prelaunch_attributed_events',prelaunch_events,
    'instrumentation_proven',instrumentation_proven,
    'postlaunch_landing_sessions',post_landing,
    'postlaunch_product_views',post_product,
    'postlaunch_offer_views',post_offer,
    'postlaunch_merchant_clickouts',post_clickout,
    'unattributed_organic_clickouts_since_launch',organic_clickouts,
    'clickout_is_sale',false,
    'network_ingestion_connected',coalesce((fm#>>'{sales_truth,network_ingestion_connected}')::boolean,false),
    'decision',decision,
    'next_move',next_move,
    'new_spend_usd',0
  );
end;
$function$;

revoke execute on function public.read_dufynd_first_money_measurement_audit_v1() from public, anon, authenticated;
grant execute on function public.read_dufynd_first_money_measurement_audit_v1() to service_role, postgres;

insert into public.dufynd_handler_contracts(handler_id,handler_version,contract,enabled)
values(
  'first_money_measurement_diagnostic',
  '1',
  jsonb_build_object(
    'handler_id','first_money_measurement_diagnostic',
    'handler_version','1',
    'certification_status','certified',
    'risk_class','low',
    'cost_class','free',
    'durability_class','durable',
    'capabilities',jsonb_build_array('commerce.read','supabase.task_state','supabase.execution_state'),
    'required_capabilities',jsonb_build_array('commerce.read','supabase.task_state','supabase.execution_state'),
    'forbidden_actions',jsonb_build_array('gmail.send','social.publish','budget.spend','main.merge','commerce.activate','shell.execute'),
    'allowed_scopes',jsonb_build_array('growth'),
    'allowed_resources',jsonb_build_array('db:dufynd.analytics','db:dufynd.first_money'),
    'allowed_tools',jsonb_build_array('read_dufynd_first_money_measurement_audit_v1','claim_dufynd_worker_v2','update_dufynd_worker_v2'),
    'verification_policy',jsonb_build_object('kind','first_money_measurement_diagnostic','version',1),
    'supports_retry',true,
    'supports_parallel_execution',false,
    'required_approval_class',null
  ),
  true
)
on conflict(handler_id,handler_version) do update
set contract=excluded.contract,enabled=excluded.enabled;

create or replace function public.plan_dufynd_measurement_work_v1()
returns jsonb
language plpgsql
set search_path to 'public'
as $function$
declare
  q jsonb;
  fm jsonb;
  tid text := 'bizplan:first-money-measurement:'||to_char(now() at time zone 'UTC','YYYYMMDD');
  created boolean := false;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-first-money-measurement-planner-v1'));
  q := public.get_dufynd_next_autonomous_action();

  if q->>'state' in ('work_available','work_in_progress','owner_gate') then
    return jsonb_build_object('version',1,'state',q->>'state','created',false,'new_spend_usd',0);
  end if;

  fm := public.read_dufynd_first_money_runtime();

  if fm->>'next_evidence'='qualified_session'
     and not exists(
       select 1 from public.dufynd_autonomy_tasks
       where task_id=tid and status='done'
     ) then
    insert into public.dufynd_autonomy_tasks(
      task_id,domain,title,instruction,status,priority,budget_class,
      resource_scope,durability_policy,durable_payload,required_capabilities,forbidden_actions
    ) values(
      tid,'growth','Diagnose First-Money measurement gap',
      'Compare launch timing with attributed analytics and determine whether the missing signal is instrumentation, distribution, offer transition or external transaction evidence. Never create traffic, click affiliate links, publish, message or spend.',
      'ready',92,'free',
      '["db:dufynd.analytics","db:dufynd.first_money"]'::jsonb,
      'durable',
      '{"kind":"first_money_measurement_diagnostic","version":1}'::jsonb,
      '["commerce.read","supabase.task_state","supabase.execution_state"]'::jsonb,
      '["gmail.send","social.publish","budget.spend","main.merge","commerce.activate","shell.execute"]'::jsonb
    ) on conflict(task_id) do nothing;
    created := found;
  end if;

  return jsonb_build_object(
    'version',1,
    'state',case when created then 'work_planned' else 'no_measurement_work_due' end,
    'created',created,
    'task_id',case when created then tid else null end,
    'new_spend_usd',0
  );
end;
$function$;

revoke execute on function public.plan_dufynd_measurement_work_v1() from public, anon, authenticated;
grant execute on function public.plan_dufynd_measurement_work_v1() to service_role, postgres;

create or replace function public.run_dufynd_measurement_worker_v1()
returns jsonb
language plpgsql
set search_path to 'public'
as $function$
declare
  t public.dufynd_autonomy_tasks;
  token uuid := gen_random_uuid();
  claimed jsonb;
  audit jsonb;
  evidence text;
  ok boolean;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-first-money-measurement-worker-v1'));

  select q.* into t
  from public.dufynd_autonomy_tasks q
  where q.status='ready'
    and q.domain='growth'
    and q.budget_class='free'
    and not q.provider_cost_unknown
    and not q.requires_human_approval
    and not q.external_review_required
    and not q.needs_freshness_recheck
    and q.durable_payload->>'kind'='first_money_measurement_diagnostic'
    and q.resource_scope='["db:dufynd.analytics","db:dufynd.first_money"]'::jsonb
    and public.dufynd_capability_list_valid(q.required_capabilities)
    and public.dufynd_capability_list_valid(q.forbidden_actions)
  order by q.priority desc,q.created_at,q.task_id
  limit 1
  for update;

  if t.task_id is null then
    return jsonb_build_object('version',1,'status','idle','reason','no_measurement_task','new_spend_usd',0);
  end if;

  claimed := public.claim_dufynd_worker_v2(t.task_id,'first_money_measurement_worker_v1',token);
  if claimed is null then
    return jsonb_build_object('version',1,'status','not_claimed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  ok := public.update_dufynd_worker_v2(
    t.task_id,token,'working',
    'Comparing launch timing with attributed First-Money analytics.',
    null
  );
  if not ok then
    return jsonb_build_object('version',1,'status','claim_update_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  audit := public.read_dufynd_first_money_measurement_audit_v1();
  evidence := 'First-Money measurement diagnostic: '||audit::text;

  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.first_money_measurement_v1','growth',audit,92,now())
  on conflict(key) do update
  set value=excluded.value,priority=excluded.priority,last_verified_at=excluded.last_verified_at;

  ok := public.update_dufynd_worker_v2(t.task_id,token,'verifying',evidence,null);
  if not ok then
    return jsonb_build_object('version',1,'status','verification_transition_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  ok := public.update_dufynd_worker_v2(t.task_id,token,'done',evidence,null);
  if not ok then
    return jsonb_build_object('version',1,'status','completion_failed','task_id',t.task_id,'new_spend_usd',0);
  end if;

  return jsonb_build_object(
    'version',1,'status','completed','task_id',t.task_id,
    'audit',audit,'new_spend_usd',0
  );
end;
$function$;

revoke execute on function public.run_dufynd_measurement_worker_v1() from public, anon, authenticated;
grant execute on function public.run_dufynd_measurement_worker_v1() to service_role, postgres;

create or replace function public.read_dufynd_safe_work_exhaustion_v1()
returns jsonb
language plpgsql
stable
set search_path to 'public'
as $function$
declare
  fm jsonb;
  m jsonb;
  day_key text := to_char(now() at time zone 'UTC','YYYYMMDD');
  content_queue_done boolean;
  content_packet_done boolean;
  content_reuse_done boolean;
  measurement_done boolean;
  executable_count integer;
  owner_gate_count integer;
  exhausted boolean;
begin
  fm := public.read_dufynd_first_money_runtime();
  m := public.read_dufynd_first_money_measurement_audit_v1();

  select exists(
    select 1 from public.dufynd_autonomy_tasks
    where task_id='bizplan:zero-budget-content-queue:'||day_key and status='done'
  ) into content_queue_done;

  select exists(
    select 1 from public.dufynd_autonomy_tasks
    where task_id like 'bizplan:content-packet:%:'||day_key and status='done'
  ) into content_packet_done;

  select exists(
    select 1 from public.dufynd_autonomy_tasks
    where task_id='bizplan:creative-recovery:'||day_key and status='done'
  ) into content_reuse_done;

  select exists(
    select 1 from public.dufynd_autonomy_tasks
    where task_id='bizplan:first-money-measurement:'||day_key and status='done'
  ) into measurement_done;

  select count(*)::integer into executable_count
  from public.dufynd_autonomy_tasks
  where status in ('ready','running');

  select count(*)::integer into owner_gate_count
  from public.dufynd_autonomy_tasks
  where status in ('waiting_human','approval_required');

  exhausted :=
    executable_count=0
    and owner_gate_count=0
    and content_queue_done
    and content_packet_done
    and content_reuse_done
    and measurement_done
    and fm->>'next_evidence'='qualified_session'
    and m->>'decision'='waiting_for_qualified_distribution_signal';

  return jsonb_build_object(
    'version',1,
    'observed_at',now(),
    'safe_internal_work_exhausted',exhausted,
    'content_queue_done',content_queue_done,
    'content_packet_done',content_packet_done,
    'content_reuse_done',content_reuse_done,
    'measurement_done',measurement_done,
    'executable_count',executable_count,
    'owner_gate_count',owner_gate_count,
    'first_money_next_evidence',fm->>'next_evidence',
    'measurement_decision',m->>'decision',
    'reason',case when exhausted then 'qualified_distribution_signal_required' else 'internal_work_or_gate_remains' end,
    'new_spend_usd',0
  );
end;
$function$;

revoke execute on function public.read_dufynd_safe_work_exhaustion_v1() from public, anon, authenticated;
grant execute on function public.read_dufynd_safe_work_exhaustion_v1() to service_role, postgres;

create or replace function public.plan_dufynd_free_work_v1()
returns jsonb
language plpgsql
set search_path to 'public'
as $function$
declare
  before_state jsonb;
  after_state jsonb;
  wake_result jsonb;
  affiliate_plan jsonb;
  content_plan jsonb;
  packet_plan jsonb;
  measurement_plan jsonb;
  business_plan jsonb;
  exhaustion jsonb;
  report jsonb;
begin
  perform pg_advisory_xact_lock(hashtext('dufynd-free-planner-v1'));
  before_state := public.get_dufynd_next_autonomous_action();

  if before_state->>'state' in ('work_available','work_in_progress','owner_gate') then
    report := jsonb_build_object(
      'version',6,'observed_at',now(),'state',before_state->>'state',
      'action','none','reason','existing_work_or_gate_already_explains_next_step',
      'queue',before_state,'new_spend_usd',0
    );
  else
    wake_result := public.wake_dufynd_purchase_freshness();
    after_state := public.get_dufynd_next_autonomous_action();

    if after_state->>'state'='work_available' then
      report := jsonb_build_object(
        'version',6,'observed_at',now(),'state','work_replenished',
        'action','purchase_freshness_wake','wake_result',wake_result,
        'queue',after_state,'new_spend_usd',0
      );
    else
      affiliate_plan := public.plan_dufynd_affiliate_work_v1();
      after_state := public.get_dufynd_next_autonomous_action();

      if after_state->>'state'='work_available' then
        report := jsonb_build_object(
          'version',6,'observed_at',now(),'state','work_replenished',
          'action','affiliate_evidence_planning','affiliate_plan',affiliate_plan,
          'queue',after_state,'new_spend_usd',0
        );
      else
        content_plan := public.plan_dufynd_zero_budget_content_work_v1();
        after_state := public.get_dufynd_next_autonomous_action();

        if after_state->>'state'='work_available' then
          report := jsonb_build_object(
            'version',6,'observed_at',now(),'state','work_replenished',
            'action','zero_budget_content_planning','content_plan',content_plan,
            'queue',after_state,'new_spend_usd',0
          );
        else
          packet_plan := public.plan_dufynd_content_packet_work_v1();
          after_state := public.get_dufynd_next_autonomous_action();

          if after_state->>'state'='work_available' then
            report := jsonb_build_object(
              'version',6,'observed_at',now(),'state','work_replenished',
              'action','content_packet_planning','content_plan',content_plan,'packet_plan',packet_plan,
              'queue',after_state,'new_spend_usd',0
            );
          else
            measurement_plan := public.plan_dufynd_measurement_work_v1();
            after_state := public.get_dufynd_next_autonomous_action();

            if after_state->>'state'='work_available' then
              report := jsonb_build_object(
                'version',6,'observed_at',now(),'state','work_replenished',
                'action','first_money_measurement_planning',
                'measurement_plan',measurement_plan,'queue',after_state,'new_spend_usd',0
              );
            else
              business_plan := public.plan_dufynd_autonomous_business_work_v1();
              after_state := public.get_dufynd_next_autonomous_action();
              exhaustion := public.read_dufynd_safe_work_exhaustion_v1();

              if coalesce((exhaustion->>'safe_internal_work_exhausted')::boolean,false) then
                report := jsonb_build_object(
                  'version',6,'observed_at',now(),'state','waiting_market_signal',
                  'action','wait_for_qualified_distribution_signal',
                  'reason','all_current_safe_zero_spend_internal_work_is_complete',
                  'exhaustion',exhaustion,'queue',after_state,
                  'master_action_required',false,'new_spend_usd',0
                );
              else
                report := jsonb_build_object(
                  'version',6,'observed_at',now(),
                  'state',case when after_state->>'state'='work_available' then 'work_replenished' else coalesce(business_plan->>'state','planner_gap') end,
                  'action','autonomous_business_planning','wake_result',wake_result,
                  'affiliate_plan',affiliate_plan,'content_plan',content_plan,'packet_plan',packet_plan,
                  'measurement_plan',measurement_plan,'business_plan',business_plan,'exhaustion',exhaustion,
                  'queue',after_state,'business_next_move',business_plan->>'business_next_move',
                  'master_action_required',false,'waiting_external_is_global_blocker',false,
                  'new_spend_usd',0
                );
              end if;
            end if;
          end if;
        end if;
      end if;
    end if;
  end if;

  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.planner_v1','jarvis',report,100,now())
  on conflict(key) do update
  set value=excluded.value,priority=excluded.priority,last_verified_at=excluded.last_verified_at;

  return report;
end;
$function$;

create or replace function public.audit_dufynd_integrity_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'public'
as $function$
declare
  q jsonb;
  fm jsonb;
  planner jsonb;
  exhaustion jsonb;
  github_sha text;
  render_sha text;
  blocked_observers integer := 0;
  stale_private_observers integer := 0;
  stale_gmail_observers integer := 0;
  stale_render_observers integer := 0;
  stalled_ready integer := 0;
  productive_handlers integer := 0;
  critical_functions_ok boolean := false;
  planner_starved boolean := false;
  last_private_broker_capture_at timestamptz;
  private_broker_scheduler_gap boolean := false;
  issues jsonb := '[]'::jsonb;
  report jsonb;
begin
  q := public.get_dufynd_next_autonomous_action();
  fm := public.read_dufynd_first_money_runtime();
  exhaustion := public.read_dufynd_safe_work_exhaustion_v1();

  select value into planner
  from public.dufynd_master_status
  where key='jarvis.planner_v1';

  select o.last_snapshot->>'sha' into github_sha
  from public.dufynd_external_observers o
  where o.observer_id='github_branch:scentai-mvp'
  limit 1;

  select o.last_snapshot->>'sha' into render_sha
  from public.dufynd_external_observers o
  where o.source_type='render' and o.enabled
  order by o.last_success_at desc nulls last
  limit 1;

  select count(*)::integer into blocked_observers
  from public.dufynd_external_observers
  where enabled and health_status='blocked_configuration';

  select count(*)::integer into stale_private_observers
  from public.dufynd_external_observers
  where enabled and source_type in ('gmail','render')
    and (
      last_success_at is null
      or last_success_at < now()-interval '20 minutes'
      or next_retry_at is null
      or next_retry_at < now()-interval '15 minutes'
    );

  select count(*)::integer into stale_gmail_observers
  from public.dufynd_external_observers
  where enabled and source_type='gmail'
    and (
      last_success_at is null
      or last_success_at < now()-interval '20 minutes'
      or next_retry_at is null
      or next_retry_at < now()-interval '15 minutes'
    );

  select count(*)::integer into stale_render_observers
  from public.dufynd_external_observers
  where enabled and source_type='render'
    and (
      last_success_at is null
      or last_success_at < now()-interval '20 minutes'
      or next_retry_at is null
      or next_retry_at < now()-interval '15 minutes'
    );

  select max(created_at) into last_private_broker_capture_at
  from public.dufynd_broker_acceptance_sessions
  where recurring_read;

  private_broker_scheduler_gap :=
    last_private_broker_capture_at is null
    or last_private_broker_capture_at < now()-interval '25 minutes';

  select count(*)::integer into stalled_ready
  from public.dufynd_autonomy_tasks
  where status='ready'
    and created_at < now()-interval '15 minutes';

  select count(*)::integer into productive_handlers
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
    and to_regprocedure('public.reconcile_dufynd_supervisor_v2()') is not null
    and to_regprocedure('public.run_dufynd_content_worker_v1()') is not null
    and to_regprocedure('public.run_dufynd_affiliate_worker_v1()') is not null
    and to_regprocedure('public.run_dufynd_content_backlog_worker_v1()') is not null
    and to_regprocedure('public.run_dufynd_content_packet_worker_v1()') is not null
    and to_regprocedure('public.run_dufynd_measurement_worker_v1()') is not null
    and to_regprocedure('public.read_dufynd_safe_work_exhaustion_v1()') is not null;

  planner_starved :=
    coalesce(q->>'state','')='planner_gap'
    and coalesce((q->>'ready_count')::integer,0)=0
    and coalesce((q->>'active_count')::integer,0)=0
    and coalesce((q->>'approval_count')::integer,0)=0
    and not coalesce((exhaustion->>'safe_internal_work_exhausted')::boolean,false)
    and coalesce(planner->>'state','')<>'waiting_market_signal'
    and (
      coalesce(fm->>'publication_verified','false')='false'
      or fm->>'next_evidence' is not null
    );

  if not critical_functions_ok then issues := issues || '"critical_runtime_function_missing"'::jsonb; end if;
  if github_sha is not null and render_sha is not null and github_sha is distinct from render_sha then
    issues := issues || '"github_render_sha_mismatch"'::jsonb;
  end if;
  if blocked_observers > 0 then issues := issues || '"blocked_observer_configuration"'::jsonb; end if;
  if stale_private_observers > 0 then issues := issues || '"private_observer_stale"'::jsonb; end if;
  if stale_gmail_observers > 0 then issues := issues || '"gmail_observer_stale"'::jsonb; end if;
  if stale_render_observers > 0 then issues := issues || '"render_observer_stale"'::jsonb; end if;
  if private_broker_scheduler_gap then issues := issues || '"private_broker_scheduler_gap"'::jsonb; end if;
  if stalled_ready > 0 then issues := issues || '"ready_work_not_claimed"'::jsonb; end if;
  if planner_starved then issues := issues || '"planner_starvation"'::jsonb; end if;
  if productive_handlers = 0 then issues := issues || '"no_productive_business_handler"'::jsonb; end if;

  report := jsonb_build_object(
    'version',3,'checked_at',now(),
    'status',case when jsonb_array_length(issues)=0 then 'healthy' else 'degraded' end,
    'issues',issues,'github_sha',github_sha,'render_sha',render_sha,
    'blocked_observers',blocked_observers,
    'stale_private_observers',stale_private_observers,
    'stale_gmail_observers',stale_gmail_observers,
    'stale_render_observers',stale_render_observers,
    'last_private_broker_capture_at',last_private_broker_capture_at,
    'private_broker_scheduler_gap',private_broker_scheduler_gap,
    'expected_private_broker_schedule_minutes',10,
    'stalled_ready',stalled_ready,'productive_handlers',productive_handlers,
    'planner_state',coalesce(planner->>'state',q->>'state'),
    'ready_count',coalesce((q->>'ready_count')::integer,0),
    'active_count',coalesce((q->>'active_count')::integer,0),
    'planner_starved',planner_starved,
    'safe_internal_work_exhausted',coalesce((exhaustion->>'safe_internal_work_exhausted')::boolean,false),
    'critical_functions_ok',critical_functions_ok,
    'owner_action_required',false,'new_spend_usd',0
  );

  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.integrity_v1','jarvis',report,100,now())
  on conflict(key) do update
  set value=excluded.value,priority=excluded.priority,last_verified_at=excluded.last_verified_at;

  return report;
end;
$function$;

do $$
declare existing_job bigint;
begin
  select jobid into existing_job from cron.job
  where jobname='dufynd-first-money-measurement-worker-v1'
  order by jobid desc limit 1;
  if existing_job is not null then perform cron.unschedule(existing_job); end if;
  perform cron.schedule(
    'dufynd-first-money-measurement-worker-v1',
    '*/2 * * * *',
    'select public.run_dufynd_measurement_worker_v1();'
  );
end
$$;

select public.plan_dufynd_free_work_v1();
select public.run_dufynd_measurement_worker_v1();
select public.plan_dufynd_free_work_v1();
select public.audit_dufynd_integrity_v1();
