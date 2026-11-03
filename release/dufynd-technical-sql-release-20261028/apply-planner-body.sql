-- Apply only after the observer migration; requires an enclosing migration transaction.
set local lock_timeout='5s';
set local statement_timeout='30s';
select pg_advisory_xact_lock(hashtext('dufynd-free-planner-v1'));
select pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
do $release_guard$
declare r record;
begin
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.plan_dufynd_free_work_v1()');
 if r.definition_md5 is null or r.definition_md5 not in ('0fb393ff9dcd50376772556c73a6d07d')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 'v' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.plan_dufynd_free_work_v1()';
 end if;
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.read_dufynd_safe_work_exhaustion_v1()');
 if r.definition_md5 is null or r.definition_md5 not in ('9b85321f0afb551ceb44700ab458eff7')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 's' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.read_dufynd_safe_work_exhaustion_v1()';
 end if;
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.poll_dufynd_observers()');
 if r.definition_md5 is null or r.definition_md5 not in ('fdbb921ba914178935e81b2d2e3bde8e')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 'v' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.poll_dufynd_observers()';
 end if;
 if to_regprocedure('public.read_dufynd_technical_work_blockers_v1()') is not null then
  raise exception 'DUFYND release requires absent helper: public.read_dufynd_technical_work_blockers_v1()';
 end if;
end;
$release_guard$;
-- Draft-only: report technical blockers independently of the commerce funnel.
-- Read current evidence; never call the writing integrity audit recursively.
-- No queue insertion, cron, network, credential, deployment or cost change.
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
    'diagnostic_only',true,'technical_repair_executed',false,'new_spend_usd',0
  );
end;
$function$;

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
  business_work_exhausted boolean;
  technical_state jsonb;
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

  business_work_exhausted := exhausted;
  technical_state := public.read_dufynd_technical_work_blockers_v1();
  exhausted := exhausted and not coalesce((technical_state->>'technical_work_remaining')::boolean,true);

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
    when coalesce((technical_state->>'technical_work_remaining')::boolean,true)
      then 'technical_remediation_required'
    when next_external_evidence is null then 'first_money_evidence_unverified_or_missing'
    else 'internal_work_or_gate_remains'
  end;

  return jsonb_build_object(
    'version',1,'observed_at',now(),
    'safe_internal_work_exhausted',exhausted,
    'business_work_exhausted',business_work_exhausted,
    'technical_work',technical_state,
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

              if coalesce(after_state->>'state','planner_gap') not in ('work_available','work_in_progress','owner_gate')
                and coalesce((exhaustion->'technical_work'->>'technical_work_remaining')::boolean,true) then
                report := jsonb_build_object(
                  'version',6,'observed_at',now(),'state','technical_remediation_required',
                  'action','diagnose_private_observer_runtime',
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

-- Preserve restricted invocation despite CREATE OR REPLACE.
revoke execute on function public.read_dufynd_safe_work_exhaustion_v1()
  from public, anon, authenticated;
grant execute on function public.read_dufynd_safe_work_exhaustion_v1()
  to service_role, postgres;
revoke execute on function public.plan_dufynd_free_work_v1()
  from public, anon, authenticated;
grant execute on function public.plan_dufynd_free_work_v1()
  to service_role, postgres;

revoke execute on function public.read_dufynd_technical_work_blockers_v1()
  from public, anon, authenticated;
grant execute on function public.read_dufynd_technical_work_blockers_v1()
  to service_role, postgres;

do $planner_postcondition$
declare r record;
begin
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.plan_dufynd_free_work_v1()');
 if r.definition_md5 is null or r.definition_md5 not in ('048fa0a0c4f114e641fd97463848dc5c')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 'v' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.plan_dufynd_free_work_v1()';
 end if;
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.poll_dufynd_observers()');
 if r.definition_md5 is null or r.definition_md5 not in ('fdbb921ba914178935e81b2d2e3bde8e')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 'v' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.poll_dufynd_observers()';
 end if;
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.read_dufynd_safe_work_exhaustion_v1()');
 if r.definition_md5 is null or r.definition_md5 not in ('df57cc1746168a917c2d0a6bfe14bc07')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 's' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.read_dufynd_safe_work_exhaustion_v1()';
 end if;
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.read_dufynd_technical_work_blockers_v1()');
 if r.definition_md5 is null or r.definition_md5 not in ('0f9e888aa4d1f853d8a0fc0e9c84cb9b')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 's' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.read_dufynd_technical_work_blockers_v1()';
 end if;
end;
$planner_postcondition$;
