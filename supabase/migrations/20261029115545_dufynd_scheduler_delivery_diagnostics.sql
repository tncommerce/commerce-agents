-- Preserve the exact production 760d function bodies except the necessary
-- independent schedule source integration. No new cron, task, activation or
-- provider write. CREATE OR REPLACE retains existing owners/private ACLs.
-- Requires the preceding GitHub scheduler delivery monitor migration.

CREATE OR REPLACE FUNCTION public.poll_dufynd_observers()
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
declare o public.dufynd_external_observers; r record; body jsonb; url text; headers jsonb; credential_health jsonb; rid bigint; result jsonb; attempted int:=0; retry int; events jsonb;
 checked_at timestamptz; dispatched_at timestamptz; receipt_error text; conditional_fingerprint text;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 begin
  perform public.poll_dufynd_public_api_health_v1();
 exception when others then
  raise log 'DUFYND public API health hook unavailable';
 end;
 begin
  perform public.poll_dufynd_public_storefront_health_v1();
 exception when others then
  raise log 'DUFYND public storefront health hook unavailable';
 end;
 begin
  perform public.poll_dufynd_github_scheduler_delivery_v1();
 exception when others then
  raise log 'DUFYND GitHub scheduler delivery hook unavailable';
 end;
 checked_at:=clock_timestamp();
 update public.dufynd_external_observers set health_status='stale',last_error='observer_success_stale'
 where enabled and source_type in ('github_branch','github_pr','github_ci','github_workflow','render','gmail') and health_status in ('healthy','degraded') and coalesce(last_success_at,last_attempt_at,'-infinity')<checked_at-make_interval(secs=>greatest(600,interval_seconds*3));
 if to_regnamespace('net') is null then return jsonb_build_object('available',false); end if;
 for o in select * from public.dufynd_external_observers where request_id is not null and source_type not in ('render','gmail') for update loop
  -- Take wall time after the shared lock and public monitor hook, never at
  -- transaction start: a delayed consumer cannot renew retained evidence.
  if not o.enabled then
   update public.dufynd_external_observers set request_id=null,request_started_at=null,
    request_kind=null,pending_cursor=null where observer_id=o.observer_id;
   continue;
  end if;
  execute 'select status_code,content,headers,timed_out,error_msg,created,count(*) over () as receipt_count from net._http_response where id=$1' into r using o.request_id;
  checked_at:=clock_timestamp();
  if r.receipt_count is null and isfinite(o.request_started_at) and o.request_started_at<=checked_at
   and o.request_started_at>checked_at-interval '60 seconds' then continue; end if;
  -- This binding belongs only to the pending GitHub request. A rejected or
  -- consumed receipt must never be reused by a second poll.
  update public.dufynd_external_observers set request_kind=null,pending_cursor=null
   where observer_id=o.observer_id and source_type in ('github_branch','github_pr','github_ci','github_workflow');
  receipt_error:=case
   when o.request_started_at is null or not isfinite(o.request_started_at) or o.request_started_at>checked_at then 'invalid_observer_request_timestamp'
   when r.receipt_count>1 then 'ambiguous_observer_receipt'
   when r.receipt_count is not null and (r.created is null or not isfinite(r.created)
     or r.created<o.request_started_at or r.created>checked_at) then 'invalid_observer_receipt_timestamp'
   when r.receipt_count is not null and r.created<checked_at-make_interval(secs=>greatest(600,o.interval_seconds*3)) then 'stale_observer_receipt'
   when r.timed_out is true or nullif(r.error_msg,'') is not null then 'external_transport_failure'
   else null end;
  if receipt_error is not null then
   perform public.dufynd_observer_failure(o.observer_id,receipt_error);
   update public.dufynd_external_observers set last_attempt_at=checked_at,
    next_retry_at=checked_at+(next_retry_at-now()) where observer_id=o.observer_id;
   continue;
  end if;
  if r.status_code=304 then
   -- 304 has no replacement body. It can revalidate only the exact validator
   -- and retained snapshot used by this conditional request. Epoch time makes
   -- the binding independent of the consuming session's TimeZone setting.
   conditional_fingerprint:=encode(sha256(convert_to(jsonb_build_array(
    o.etag,o.last_snapshot,extract(epoch from o.last_success_at),
    o.request_id,extract(epoch from o.request_started_at))::text,'UTF8')),'hex');
   if o.source_type not in ('github_branch','github_pr','github_ci','github_workflow')
    or o.request_kind is distinct from 'github_conditional'
    or o.pending_cursor is distinct from conditional_fingerprint
    or nullif(o.etag,'') is null or jsonb_typeof(o.last_snapshot) is distinct from 'object'
    or coalesce(o.last_snapshot->>'sha','') !~ '^[a-f0-9]{40}$'
    or o.last_success_at is null or not isfinite(o.last_success_at) or o.last_success_at>o.request_started_at
    or nullif(r.content,'') is not null
    or (coalesce(r.headers->>'etag',r.headers->>'ETag') is not null
        and coalesce(r.headers->>'etag',r.headers->>'ETag') is distinct from o.etag) then
    update public.dufynd_external_observers set etag=null where observer_id=o.observer_id;
    perform public.dufynd_observer_failure(o.observer_id,'invalid_observer_not_modified');
   update public.dufynd_external_observers set last_attempt_at=checked_at,
    next_retry_at=checked_at+(next_retry_at-now()) where observer_id=o.observer_id;
    continue;
   end if;
   update public.dufynd_external_observers set last_success_at=r.created,health_status='healthy',consecutive_failures=0,last_error=null,
    request_id=null,request_started_at=null,next_retry_at=checked_at+make_interval(secs=>interval_seconds) where observer_id=o.observer_id;
   continue;
  end if;
  if r.status_code is distinct from 200 then
   retry:=case when coalesce(r.headers->>'retry-after','') ~ '^[0-9]{1,5}$' then least(3600,(r.headers->>'retry-after')::int) else null end;
   perform public.dufynd_observer_failure(o.observer_id,case when r.status_code=404 and o.source_type='gmail' then 'gmail_history_expired'
    when r.status_code=429 or (r.status_code=403 and r.headers->>'x-ratelimit-remaining'='0') then 'rate_limited' else 'external_transport_failure' end,coalesce(r.status_code,0),retry);
   update public.dufynd_external_observers set last_attempt_at=checked_at,
    next_retry_at=checked_at+(next_retry_at-now()) where observer_id=o.observer_id;
   continue;
  end if;
  begin
   body:=r.content::jsonb;
   if o.source_type='gmail' and o.request_kind='history' then
    events:=public.normalize_dufynd_observation(o.source_type,o.source_id,body,o.config);
    if jsonb_array_length(events)>0 then
     update public.dufynd_external_observers set pending_cursor=body->>'historyId',pending_page_token=body->>'nextPageToken',request_id=null,request_kind='thread',next_retry_at=now() where observer_id=o.observer_id;
     continue; -- Known thread metadata on next request, never whole mailbox content.
    end if;
   end if;
   result:=public.capture_dufynd_observation(o.observer_id,body);
   if result->>'accepted' is distinct from 'true' then
    perform public.dufynd_observer_failure(o.observer_id,'observation_not_accepted');
   update public.dufynd_external_observers set last_attempt_at=checked_at,
    next_retry_at=checked_at+(next_retry_at-now()) where observer_id=o.observer_id;
    continue;
   end if;
   if o.source_type='gmail' and o.request_kind='thread' and o.pending_cursor is not null then
    update public.dufynd_external_observers set last_cursor=case when o.pending_page_token is not null then o.last_cursor else o.pending_cursor end,
      page_token=o.pending_page_token,pending_cursor=null,pending_page_token=null,request_kind=null where observer_id=o.observer_id;
   end if;
   -- capture owns normalization and deduplicated events. Only after acceptance
   -- retain the actual receipt time and replace (including clear) its validator.
   update public.dufynd_external_observers set last_success_at=r.created,last_attempt_at=o.request_started_at,
    next_retry_at=checked_at+make_interval(secs=>interval_seconds),
    etag=nullif(coalesce(r.headers->>'etag',r.headers->>'ETag'),'') where observer_id=o.observer_id;
  exception when others then
   perform public.dufynd_observer_failure(o.observer_id,'invalid_bounded_source_response');
   update public.dufynd_external_observers set last_attempt_at=checked_at,
    next_retry_at=checked_at+(next_retry_at-now()) where observer_id=o.observer_id;
  end;
 end loop;
 -- External providers are private-broker only, never a broad Vault key read.
 for o in select * from public.dufynd_external_observers where enabled and source_type in ('render','gmail') loop
  update public.dufynd_external_observers set request_id=null,request_started_at=null where observer_id=o.observer_id;
  credential_health:=public.get_dufynd_credential_health(o.source_type);
  if not coalesce((credential_health->>'activation_enabled')::boolean,false)
   or credential_health->>'status' not in ('healthy','expiring') then
   update public.dufynd_external_observers set health_status='blocked_configuration',
    last_error=case when credential_health->>'status' in ('healthy','expiring') then 'broker_activation_required' else 'credential_'||(credential_health->>'status') end,
    request_id=null,request_started_at=null where observer_id=o.observer_id;
  end if;
 end loop;
 select * into o from public.dufynd_external_observers where enabled and source_type in ('github_branch','github_pr','github_ci','github_workflow')
  and request_id is null and next_retry_at<=clock_timestamp() order by next_retry_at,last_attempt_at nulls first limit 1 for update;
 if not found then return jsonb_build_object('attempted',0); end if;
 headers:='{"Accept":"application/json","User-Agent":"DUFYND-Supervisor-V2","X-GitHub-Api-Version":"2022-11-28"}';
 if nullif(o.etag,'') is not null and jsonb_typeof(o.last_snapshot)='object'
  and coalesce(o.last_snapshot->>'sha','') ~ '^[a-f0-9]{40}$'
  and isfinite(o.last_success_at) and o.last_success_at<=clock_timestamp() then
  headers:=headers||jsonb_build_object('If-None-Match',o.etag);
 end if;
 if o.source_type='github_branch' then url:='https://api.github.com/repos/tncommerce/commerce-agents/branches/scentai-mvp';
 elsif o.source_type='github_pr' then url:='https://api.github.com/repos/tncommerce/commerce-agents/pulls/'||o.source_id;
 elsif o.source_type in ('github_ci','github_workflow') then url:='https://api.github.com/repos/tncommerce/commerce-agents/actions/runs/'||o.source_id;
 else return jsonb_build_object('attempted',0); end if;
 dispatched_at:=clock_timestamp();
 execute 'select net.http_get(url:=$1,headers:=$2,timeout_milliseconds:=5000)' into rid using url,headers;
 update public.dufynd_external_observers set request_id=rid,request_started_at=dispatched_at,last_attempt_at=dispatched_at,
  request_kind=case when headers ? 'If-None-Match' then 'github_conditional' else 'github_get' end,
  pending_cursor=case when headers ? 'If-None-Match' then encode(sha256(convert_to(jsonb_build_array(
   o.etag,o.last_snapshot,extract(epoch from o.last_success_at),rid,extract(epoch from dispatched_at))::text,'UTF8')),'hex') else null end
  where observer_id=o.observer_id;
 return jsonb_build_object('attempted',1);
end $function$;

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
  render_release_state jsonb;
  github_sha text;
  github_observed_at timestamptz;
  last_acceptance_started_at timestamptz;
  last_broker_capture_at timestamptz;
  acceptance_gap boolean;
  public_health jsonb;
  storefront_health jsonb;
  scheduler_delivery jsonb;
  scheduler_issue text;
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

  render_release_state := public.read_dufynd_render_release_expectations_v1();
  github_sha := render_release_state->>'repository_head_sha';
  github_observed_at := (render_release_state->>'github_observed_at')::timestamptz;
  render_mismatch_count := (render_release_state->>'revision_mismatch_count')::integer;

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

  if github_sha is null or github_sha !~ '^[a-f0-9]{40}$' then
    issues := issues || '"production_revision_unverified"'::jsonb;
  end if;
  issues := issues || (render_release_state->'issues');
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

  storefront_health := public.read_dufynd_public_storefront_health_v1();
  if storefront_health->'enabled'='true'::jsonb
    and storefront_health->'healthy' is distinct from 'true'::jsonb then
    issues := issues || jsonb_build_array(case storefront_health->>'status'
      when 'pending' then 'public_storefront_health_pending'
      when 'stale' then 'public_storefront_health_stale'
      when 'unhealthy' then 'public_storefront_unhealthy'
      else 'public_storefront_health_unavailable'
    end);
  end if;

  -- Actual event=schedule/main API receipts, independent of manual Render reads
  -- and acceptance sessions. Observation, delivery and dispatch stay separate.
  scheduler_delivery := public.read_dufynd_github_scheduler_delivery_v1();
  private_work_remaining := private_work_remaining
    or scheduler_delivery->'healthy' is distinct from 'true'::jsonb;
  -- Disabled/missing monitoring is unknown evidence, not a healthy scheduler.
  if jsonb_typeof(scheduler_delivery->'issues')='array' then
    for scheduler_issue in select jsonb_array_elements_text(scheduler_delivery->'issues') loop
      if not (issues ? scheduler_issue) then
        issues := issues || jsonb_build_array(scheduler_issue);
      end if;
    end loop;
    if jsonb_array_length(scheduler_delivery->'issues')=0
      and scheduler_delivery->'healthy' is distinct from 'true'::jsonb then
      issues := issues || '"github_scheduler_observation_unavailable"'::jsonb;
    end if;
  else
    issues := issues || '"github_scheduler_observation_unavailable"'::jsonb;
  end if;

  return jsonb_build_object(
    'version',1,'observed_at',now(),
    'status',case when jsonb_array_length(issues)=0 then 'healthy' else 'degraded' end,
    'technical_work_remaining',jsonb_array_length(issues)>0,'issues',issues,
    'enabled_private_observers',private_count,'blocked_observers',blocked_count,
    'stale_private_observers',stale_count,'unhealthy_private_observers',unhealthy_count,
    'render_revision_mismatches',render_mismatch_count,
    'render_release_expectations',render_release_state,
    'github_sha',github_sha,'github_observed_at',github_observed_at,
    'last_acceptance_started_at',last_acceptance_started_at,
    'last_broker_complete_capture_at',last_broker_capture_at,
    'private_broker_acceptance_gap',acceptance_gap,
    'private_technical_work_remaining',private_work_remaining,
    'public_api_health',public_health,
    'public_storefront_health',storefront_health,
    'github_scheduler_delivery',scheduler_delivery,
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
                    then 'diagnose_public_api_health'
                    when exhaustion->'technical_work'->'public_storefront_health'->'enabled'='true'::jsonb
                      and exhaustion->'technical_work'->'public_storefront_health'->'healthy' is distinct from 'true'::jsonb
                    then 'diagnose_public_storefront_health'
                    when exhaustion->'technical_work'->'github_scheduler_delivery'->'healthy' is distinct from 'true'::jsonb
                    then 'diagnose_private_scheduler_delivery'
                    else 'diagnose_private_observer_runtime' end,
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
  planner_verified_at timestamptz;
  technical_diagnosis_current boolean := false;
  technical_issue text;
  exhaustion jsonb;
  github_sha text;
  render_sha text;
  render_release_state jsonb;
  blocked_observers integer := 0;
  stale_private_observers integer := 0;
  stale_gmail_observers integer := 0;
  stale_render_observers integer := 0;
  stalled_ready integer := 0;
  productive_handlers integer := 0;
  critical_functions_ok boolean := false;
  planner_starved boolean := false;
  last_private_broker_capture_at timestamptz;
  last_private_broker_acceptance_started_at timestamptz;
  private_broker_acceptance_gap boolean;
  scheduler_delivery jsonb;
  private_broker_scheduler_gap boolean;
  issues jsonb := '[]'::jsonb;
  report jsonb;
begin
  q := public.get_dufynd_next_autonomous_action();
  fm := public.read_dufynd_first_money_runtime();
  exhaustion := public.read_dufynd_safe_work_exhaustion_v1();

  select value,last_verified_at into planner,planner_verified_at
  from public.dufynd_master_status
  where key='jarvis.planner_v1';

  render_release_state := public.read_dufynd_render_release_expectations_v1();
  github_sha := render_release_state->>'repository_head_sha';

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

  -- Acceptance/capture freshness cannot establish natural schedule delivery.
  -- Reuse the current reader's independently validated, differently named facts.
  last_private_broker_acceptance_started_at :=
    (exhaustion->'technical_work'->>'last_acceptance_started_at')::timestamptz;
  last_private_broker_capture_at :=
    (exhaustion->'technical_work'->>'last_broker_complete_capture_at')::timestamptz;
  private_broker_acceptance_gap :=
    (exhaustion->'technical_work'->>'private_broker_acceptance_gap')::boolean;
  scheduler_delivery := exhaustion->'technical_work'->'github_scheduler_delivery';
  private_broker_scheduler_gap := case
    when scheduler_delivery->'enabled'='true'::jsonb
      and jsonb_typeof(scheduler_delivery->'delivery_gap')='boolean'
    then (scheduler_delivery->>'delivery_gap')::boolean
    else null end;

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

  -- A current, independently confirmed monitoring diagnosis explains an empty
  -- queue. A stale marker or a now-resolved issue cannot hide real starvation.
  technical_diagnosis_current := coalesce(
    planner->>'state'='technical_remediation_required'
    and planner->'technical_work'->'technical_work_remaining'='true'::jsonb
    and exhaustion->'technical_work'->'technical_work_remaining'='true'::jsonb
    and isfinite(planner_verified_at)
    and planner_verified_at<=statement_timestamp()
    and planner_verified_at>=statement_timestamp()-interval '600 seconds',false);

  planner_starved :=
    coalesce(q->>'state','')='planner_gap'
    and coalesce((q->>'ready_count')::integer,0)=0
    and coalesce((q->>'active_count')::integer,0)=0
    and coalesce((q->>'approval_count')::integer,0)=0
    and not coalesce((exhaustion->>'safe_internal_work_exhausted')::boolean,false)
    and coalesce(planner->>'state','')<>'waiting_market_signal'
    and not technical_diagnosis_current
    and (
      coalesce(fm->>'publication_verified','false')='false'
      or fm->>'next_evidence' is not null
    );

  if not critical_functions_ok then issues := issues || '"critical_runtime_function_missing"'::jsonb; end if;
  issues := issues || (render_release_state->'issues');
  if blocked_observers > 0 then issues := issues || '"blocked_observer_configuration"'::jsonb; end if;
  if stale_private_observers > 0 then issues := issues || '"private_observer_stale"'::jsonb; end if;
  if stale_gmail_observers > 0 then issues := issues || '"gmail_observer_stale"'::jsonb; end if;
  if stale_render_observers > 0 then issues := issues || '"render_observer_stale"'::jsonb; end if;
  if private_broker_acceptance_gap then issues := issues || '"private_broker_acceptance_gap"'::jsonb; end if;
  if stalled_ready > 0 then issues := issues || '"ready_work_not_claimed"'::jsonb; end if;
  if planner_starved then issues := issues || '"planner_starvation"'::jsonb; end if;
  if productive_handlers = 0 then issues := issues || '"no_productive_business_handler"'::jsonb; end if;

  -- Removing a false starvation cause must not erase the real private capture
  -- or public-health blocker that explains it. Preserve each current issue once.
  if jsonb_typeof(exhaustion->'technical_work'->'issues')='array' then
    for technical_issue in select jsonb_array_elements_text(exhaustion->'technical_work'->'issues') loop
      if not (issues ? technical_issue) then issues := issues || jsonb_build_array(technical_issue); end if;
    end loop;
  end if;

  report := jsonb_build_object(
    'version',3,'checked_at',now(),
    'status',case when jsonb_array_length(issues)=0 then 'healthy' else 'degraded' end,
    'issues',issues,'github_sha',github_sha,'render_sha',render_sha,
    'render_release_expectations',render_release_state,
    'render_revision_mismatches',(render_release_state->>'revision_mismatch_count')::integer,
    'blocked_observers',blocked_observers,
    'stale_private_observers',stale_private_observers,
    'stale_gmail_observers',stale_gmail_observers,
    'stale_render_observers',stale_render_observers,
    'last_private_broker_capture_at',last_private_broker_capture_at,
    'last_private_broker_acceptance_started_at',last_private_broker_acceptance_started_at,
    'private_broker_acceptance_gap',private_broker_acceptance_gap,
    'private_broker_scheduler_gap',private_broker_scheduler_gap,
    'private_broker_scheduler_observation_status',scheduler_delivery->'transport_status',
    'github_scheduler_delivery',scheduler_delivery,
    'expected_private_broker_schedule_minutes',10,
    'stalled_ready',stalled_ready,'productive_handlers',productive_handlers,
    'planner_state',coalesce(planner->>'state',q->>'state'),
    'ready_count',coalesce((q->>'ready_count')::integer,0),
    'active_count',coalesce((q->>'active_count')::integer,0),
    'planner_starved',planner_starved,
    'technical_diagnosis_current',technical_diagnosis_current,
    'technical_work',exhaustion->'technical_work',
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
