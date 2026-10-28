-- Add independently measured public API liveness to existing technical truth.
-- Disabled monitoring preserves the current planner behavior. No task is added;
-- public success cannot clear private provider, source-revision or capture gaps.
create or replace function public.read_dufynd_technical_work_blockers_v1()
returns jsonb
language plpgsql
stable
security invoker
set search_path to 'public'
as $function$
declare
  private_count integer;
  blocked_count integer;
  stale_count integer;
  unhealthy_count integer;
  render_count integer;
  render_mismatch_count integer;
  github_sha text;
  github_observed_at timestamptz;
  last_acceptance_started_at timestamptz;
  last_broker_capture_at timestamptz;
  acceptance_gap boolean;
  public_health jsonb;
  private_work_remaining boolean;
  issues jsonb := '[]'::jsonb;
begin
  select count(*)::integer,
    count(*) filter (where health_status='blocked_configuration')::integer,
    count(*) filter (where last_success_at is null
      or last_success_at < now()-make_interval(secs=>greatest(600,interval_seconds*3))
      or last_success_at > now()+interval '5 minutes')::integer,
    count(*) filter (where health_status is distinct from 'healthy')::integer,
    count(*) filter (where source_type='render')::integer
  into private_count,blocked_count,stale_count,unhealthy_count,render_count
  from public.dufynd_external_observers
  where enabled and source_type in ('render','gmail');

  select last_snapshot->>'sha',last_success_at into github_sha,github_observed_at
  from public.dufynd_external_observers
  where observer_id='github_branch:scentai-mvp' and enabled
    and health_status='healthy'
    and last_success_at >= now()-make_interval(secs=>greatest(600,interval_seconds*3))
    and last_success_at <= now()+interval '5 minutes';

  select count(*)::integer into render_mismatch_count
  from public.dufynd_external_observers
  where enabled and source_type='render'
    and github_sha ~ '^[a-f0-9]{40}$'
    and last_snapshot->>'sha' is distinct from github_sha;

  select max(s.created_at),max(s.finalized_at) filter (
      where s.status='activated' and s.source_sha=github_sha
        and s.finalized_at >= s.created_at
        and s.finalized_at <= now()+interval '5 minutes'
        and not exists (select 1 from public.dufynd_external_observers o
          where o.enabled and o.source_type in ('render','gmail')
            and not (s.captured_observers ? o.observer_id)))
    into last_acceptance_started_at,last_broker_capture_at
  from public.dufynd_broker_acceptance_sessions s
  where s.recurring_read and s.created_at <= now()+interval '5 minutes';
  acceptance_gap := private_count>0 and (last_acceptance_started_at is null
    or last_acceptance_started_at < now()-interval '25 minutes');

  if render_count=0 then issues := issues || '"render_monitor_missing"'::jsonb; end if;
  if github_sha is null or github_sha !~ '^[a-f0-9]{40}$' then
    issues := issues || '"production_revision_unverified"'::jsonb;
  end if;
  if render_mismatch_count>0 then issues := issues || '"github_render_sha_mismatch"'::jsonb; end if;
  if blocked_count>0 then issues := issues || '"blocked_observer_configuration"'::jsonb; end if;
  if stale_count>0 then issues := issues || '"private_observer_stale"'::jsonb; end if;
  if unhealthy_count>0 then issues := issues || '"private_observer_unhealthy"'::jsonb; end if;
  if acceptance_gap then issues := issues || '"private_broker_acceptance_gap"'::jsonb; end if;
  -- A recent failed/partial acceptance is not a completed capture.
  -- Absence of an acceptance does not prove that the scheduler stopped.
  if private_count>0 and (last_broker_capture_at is null
    or last_broker_capture_at < now()-interval '25 minutes') then
    issues := issues || '"private_broker_capture_unverified"'::jsonb;
  end if;

  -- Evaluate freshness at read time; a stopped cron cannot preserve healthy.
  -- The public endpoint never replaces any private-provider or capture proof.
  private_work_remaining := jsonb_array_length(issues)>0;
  public_health := public.read_dufynd_public_api_health_v1();
  if public_health->'enabled'='true'::jsonb
    and public_health->'healthy' is distinct from 'true'::jsonb then
    issues := issues || jsonb_build_array(case public_health->>'status'
      when 'pending' then 'public_api_health_pending'
      when 'stale' then 'public_api_health_stale'
      when 'unhealthy' then 'public_api_unhealthy'
      else 'public_api_health_unavailable'
    end);
  end if;

  return jsonb_build_object(
    'version',1,'observed_at',now(),
    'status',case when jsonb_array_length(issues)=0 then 'healthy' else 'degraded' end,
    'technical_work_remaining',jsonb_array_length(issues)>0,'issues',issues,
    'enabled_private_observers',private_count,'blocked_observers',blocked_count,
    'stale_private_observers',stale_count,'unhealthy_private_observers',unhealthy_count,
    'render_revision_mismatches',render_mismatch_count,
    'github_sha',github_sha,'github_observed_at',github_observed_at,
    'last_acceptance_started_at',last_acceptance_started_at,
    'last_broker_complete_capture_at',last_broker_capture_at,
    'private_broker_acceptance_gap',acceptance_gap,
    'private_technical_work_remaining',private_work_remaining,
    'public_api_health',public_health,
    'diagnostic_only',true,'technical_repair_executed',false,'new_spend_usd',0
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

              if coalesce(after_state->>'state','planner_gap') not in ('work_available','work_in_progress','owner_gate')
                and coalesce((exhaustion->'technical_work'->>'technical_work_remaining')::boolean,true) then
                report := jsonb_build_object(
                  'version',6,'observed_at',now(),'state','technical_remediation_required',
                  'action',case when exhaustion->'technical_work'->'public_api_health'->'enabled'='true'::jsonb
                    and exhaustion->'technical_work'->'public_api_health'->'healthy' is distinct from 'true'::jsonb
                    then 'diagnose_public_api_health' else 'diagnose_private_observer_runtime' end,
                  'reason','monitoring_blockers_prevent_global_work_exhaustion',
                  'operational_state','degraded','technical_work',exhaustion->'technical_work',
                  'technical_repair_executed',false,
                  'next_external_evidence',exhaustion->>'next_external_evidence',
                  'exhaustion',exhaustion,'queue',after_state,
                  'master_action_required',false,'new_spend_usd',0
                );
              elsif coalesce((exhaustion->>'safe_internal_work_exhausted')::boolean,false) then
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

-- Preserve the existing owner/service-role-only contracts.
revoke execute on function public.read_dufynd_technical_work_blockers_v1()
  from public, anon, authenticated;
grant execute on function public.read_dufynd_technical_work_blockers_v1()
  to service_role, postgres;
revoke execute on function public.plan_dufynd_free_work_v1()
  from public, anon, authenticated;
grant execute on function public.plan_dufynd_free_work_v1()
  to service_role, postgres;
