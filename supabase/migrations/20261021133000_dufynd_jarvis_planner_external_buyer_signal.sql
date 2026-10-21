-- DUFYND Jarvis Planner 2026-10-21: classify a proven external buyer-signal wait.
-- Exact definitions captured read-only from live Supabase on the production HEAD
-- 1ff02b04f0243e6be1043993fcd7aa936751fabc.
-- NO cron changes, tasks, synthetic analytics, network calls, or publication.
-- DEPLOYMENT HOLD: this migration is DEV-only until separate production GO.
-- Idempotently replace only these two functions; preserve signatures and grants.
--
-- The existing measurement planner produces no task when next_evidence is
-- merchant_clickout. The old exhaustion predicate required measurement_done
-- and qualified_session; it therefore claimed a planner_gap forever, even
-- with zero runnable tasks and no remaining internal safe work.
-- Buyer action and network commission are EXTERNAL signals, never invented.
--
CREATE OR REPLACE FUNCTION public.read_dufynd_safe_work_exhaustion_v1()
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE
 SET search_path TO 'public'
AS $function$
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
  awaiting_buyer boolean;
  awaiting_distribution boolean;
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


  -- A genuine merchant clickout depends on an external visitor action.
  -- The measurement planner intentionally does NOT create a diagnostic task
  -- for this stage, so measurement_done=false must not mean actionable work.
  -- Never claim the condition is a confirmed sale or that a social click occurred.
  awaiting_buyer :=
    fm->>'next_evidence'='merchant_clickout'
    and m->>'decision'='qualified_traffic_present_no_clickout';
  awaiting_distribution :=
    fm->>'next_evidence'='qualified_session'
    and m->>'decision'='waiting_for_qualified_distribution_signal'
    and measurement_done;

  exhausted :=
    executable_count=0
    and owner_gate_count=0
    and content_queue_done
    and content_packet_done
    and content_reuse_done
    and (awaiting_buyer or awaiting_distribution);

  return jsonb_build_object(
    'version',1,
    'observed_at',now(),
    'safe_internal_work_exhausted',exhausted,
    'waiting_signal',case
      when exhausted and awaiting_buyer then 'merchant_clickout'
      when exhausted and awaiting_distribution then 'qualified_session'
      else null
    end,
    'content_queue_done',content_queue_done,
    'content_packet_done',content_packet_done,
    'content_reuse_done',content_reuse_done,
    'measurement_done',measurement_done,
    'executable_count',executable_count,
    'owner_gate_count',owner_gate_count,
    'first_money_next_evidence',fm->>'next_evidence',
    'measurement_decision',m->>'decision',
    'reason',case
      when exhausted and awaiting_buyer then 'genuine_merchant_clickout_required'
      when exhausted and awaiting_distribution then 'qualified_distribution_signal_required'
      else 'internal_work_or_gate_remains'
    end,
    'new_spend_usd',0
  );
end;
$function$;

CREATE OR REPLACE FUNCTION public.plan_dufynd_free_work_v1()
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
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
                  'version',6,'observed_at',now(),
                  'state',case when exhaustion->>'waiting_signal'='merchant_clickout'
                    then 'waiting_buyer_signal' else 'waiting_market_signal' end,
                  'action',case when exhaustion->>'waiting_signal'='merchant_clickout'
                    then 'wait_for_genuine_merchant_clickout' else 'wait_for_qualified_distribution_signal' end,
                  'reason',exhaustion->>'reason',
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
