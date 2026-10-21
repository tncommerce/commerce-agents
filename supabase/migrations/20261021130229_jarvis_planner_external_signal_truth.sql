-- DUFYND Jarvis planner truth boundary (DEV / DRAFT ONLY).
-- Derived from the exact production definitions on 2026-10-21; no queue,
-- cron, network, price, product, consent or publisher changes.
--
-- A daily first-money measurement task is only due while the next evidence
-- is a qualified session. Once the funnel is at merchant_clickout or network
-- transaction evidence, "measurement_done = false" is NOT missing internal
-- measurement work. Do not invent tasks to satisfy the old conjunct.
--
-- Keep legacy report versions and existing permissions; add explicit,
-- falsifiable next-evidence fields and account for active leases/owner gates.

create or replace function public.read_dufynd_safe_work_exhaustion_v1()
returns jsonb
language plpgsql
stable
set search_path to 'public'
as $function$
declare
  fm jsonb;
  m jsonb;
  queue_state jsonb;
  day_key text := to_char(now() at time zone 'UTC','YYYYMMDD');
  content_queue_done boolean;
  content_packet_done boolean;
  content_reuse_done boolean;
  measurement_done boolean;
  measurement_work_due boolean;
  measurement_gate_satisfied boolean;
  next_external_evidence text;
  executable_count integer;
  owner_gate_count integer;
  blocked_transport_count integer;
  exhausted boolean;
  reason text;
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

  -- Reuse the actual queue's lease/approval classification. A task with an
  -- active lease or a human gate is NOT a completed/no-work condition.
  queue_state := public.get_dufynd_next_autonomous_action();
  executable_count := coalesce((queue_state->>'ready_count')::integer,0)
                    + coalesce((queue_state->>'active_count')::integer,0);
  owner_gate_count := coalesce((queue_state->>'waiting_human_count')::integer,0)
                    + coalesce((queue_state->>'approval_count')::integer,0);

  -- Report real technical dead letters separately. A blocked task is not a
  -- safe runnable task and must not be revived merely to fill the queue.
  select count(*)::integer into blocked_transport_count
  from public.dufynd_autonomy_tasks
  where status='blocked' and blocked_reason='transport_unverified';

  -- Require exact alignment between the first-party next-evidence marker and
  -- the independent measurement audit. Unknown or conflicting evidence fails
  -- closed; a clickout is never a sale and never a proven network commission.
  next_external_evidence := case
    when fm->>'next_evidence'='qualified_session'
     and m->>'decision'='waiting_for_qualified_distribution_signal'
      then 'qualified_session'
    when fm->>'next_evidence'='merchant_clickout'
     and m->>'decision'='qualified_traffic_present_no_clickout'
      then 'merchant_clickout'
    when fm->>'next_evidence'='affiliate_transaction_evidence'
     and m->>'decision'='attributed_clickout_signal_present'
      then 'affiliate_transaction_evidence'
    else null
  end;

  -- Existing plan_dufynd_measurement_work_v1 creates a daily diagnostic only
  -- for next_evidence='qualified_session'. Keep measurement_done as the REAL
  -- completion flag; report separately that later stages have no task due.
  measurement_work_due := fm->>'next_evidence'='qualified_session';
  measurement_gate_satisfied := case
    when next_external_evidence='qualified_session' then measurement_done
    when next_external_evidence in ('merchant_clickout','affiliate_transaction_evidence')
      then true
    else false
  end;

  exhausted :=
    queue_state->>'state'='planner_gap'
    and executable_count=0
    and owner_gate_count=0
    and content_queue_done
    and content_packet_done
    and content_reuse_done
    and measurement_gate_satisfied
    and next_external_evidence is not null;

  reason := case
    when exhausted and next_external_evidence='qualified_session'
      then 'qualified_distribution_signal_required'
    when exhausted and next_external_evidence='merchant_clickout'
      then 'merchant_clickout_signal_required'
    when exhausted and next_external_evidence='affiliate_transaction_evidence'
      then 'original_network_transaction_evidence_required'
    when queue_state->>'state'='work_available' then 'certified_work_available'
    when queue_state->>'state'='work_in_progress' then 'certified_work_in_progress'
    when queue_state->>'state'='owner_gate' then 'owner_approval_required'
    when next_external_evidence is null then 'first_money_evidence_unverified_or_missing'
    else 'internal_work_or_gate_remains'
  end;

  return jsonb_build_object(
    'version',1,'observed_at',now(),
    'safe_internal_work_exhausted',exhausted,
    'content_queue_done',content_queue_done,
    'content_packet_done',content_packet_done,
    'content_reuse_done',content_reuse_done,
    'measurement_done',measurement_done,
    'measurement_work_due',measurement_work_due,
    'measurement_gate_satisfied',measurement_gate_satisfied,
    'executable_count',executable_count,
    'owner_gate_count',owner_gate_count,
    'queue_state',queue_state->>'state',
    'blocked_transport_count',blocked_transport_count,
    'next_external_evidence',next_external_evidence,
    'first_money_next_evidence',fm->>'next_evidence',
    'measurement_decision',m->>'decision',
    'reason',reason,'new_spend_usd',0
  );
end;
$function$;

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
  external_evidence text;
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
    -- Existing deterministic plans only. No new task type, scheduler or
    -- external execution is added by this patch.
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
              'action','content_packet_planning','content_plan',content_plan,
              'packet_plan',packet_plan,'queue',after_state,'new_spend_usd',0
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
                external_evidence := exhaustion->>'next_external_evidence';
                report := jsonb_build_object(
                  'version',6,'observed_at',now(),'state','waiting_market_signal',
                  'action',case external_evidence
                    when 'qualified_session' then 'wait_for_qualified_distribution_signal'
                    when 'merchant_clickout' then 'wait_for_verified_merchant_clickout'
                    when 'affiliate_transaction_evidence' then 'wait_for_original_network_transaction'
                  end,
                  'reason','no_certified_safe_work_currently_executable',
                  'next_external_evidence',external_evidence,
                  'blocked_transport_count',exhaustion->'blocked_transport_count',
                  'measurement_plan',measurement_plan,
                  'exhaustion',exhaustion,'queue',after_state,
                  'master_action_required',false,'new_spend_usd',0
                );
              else
                report := jsonb_build_object(
                  'version',6,'observed_at',now(),
                  'state',case
                    when after_state->>'state'='work_available' then 'work_replenished'
                    when after_state->>'state'='work_in_progress' then 'work_in_progress'
                    when after_state->>'state'='owner_gate' then 'owner_gate'
                    else coalesce(business_plan->>'state','planner_gap')
                  end,
                  'action','autonomous_business_planning','wake_result',wake_result,
                  'affiliate_plan',affiliate_plan,'content_plan',content_plan,
                  'packet_plan',packet_plan,
                  'measurement_plan',measurement_plan,'business_plan',business_plan,
                  'exhaustion',exhaustion,'queue',after_state,
                  'business_next_move',business_plan->>'business_next_move',
                  'master_action_required',false,
                  'waiting_external_is_global_blocker',false,'new_spend_usd',0
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

-- Preserve restricted invocation despite CREATE OR REPLACE.
revoke execute on function public.read_dufynd_safe_work_exhaustion_v1()
  from public, anon, authenticated;
grant execute on function public.read_dufynd_safe_work_exhaustion_v1()
  to service_role, postgres;
revoke execute on function public.plan_dufynd_free_work_v1()
  from public, anon, authenticated;
grant execute on function public.plan_dufynd_free_work_v1()
  to service_role, postgres;
