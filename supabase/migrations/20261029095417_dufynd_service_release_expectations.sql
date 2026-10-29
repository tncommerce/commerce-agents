-- A repository revision is not every service's approved deployment revision.
-- Read one private, explicitly approved release intent bound to the exact fresh
-- repository HEAD. This migration never seeds approvals or provider evidence.
CREATE OR REPLACE FUNCTION public.read_dufynd_render_release_expectations_v1()
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path TO 'public'
AS $function$
DECLARE
  checked_at timestamptz := statement_timestamp();
  approval jsonb;
  reviewed_at timestamptz;
  approved_at timestamptz;
  valid_until timestamptz;
  approved_services jsonb := '{}';
  binding_reason text;
  iso_timestamp text := '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?(Z|[+-][0-9]{2}:[0-9]{2})$';
  github_sha text;
  github_observed_at timestamptz;
  item jsonb;
  target record;
  observer public.dufynd_external_observers;
  observer_count integer;
  source_valid boolean;
  snapshot_valid boolean;
  observation_verified boolean;
  observation_reason text;
  intent_match boolean;
  comparison_status text;
  observed_sha text;
  services jsonb := '[]';
  issues jsonb := '[]';
  extra_count integer := 0;
  missing_count integer := 0;
  unverified_count integer := 0;
  unknown_count integer := 0;
  mismatch_count integer := 0;
BEGIN
  SELECT last_snapshot->>'sha',last_success_at INTO github_sha,github_observed_at
  FROM public.dufynd_external_observers
  WHERE observer_id='github_branch:scentai-mvp'
    AND source_type='github_branch' AND source_id='scentai-mvp'
    AND enabled AND health_status='healthy'
    AND jsonb_typeof(last_snapshot)='object'
    AND jsonb_typeof(last_snapshot->'sha')='string'
    AND last_snapshot->>'sha' ~ '^[a-f0-9]{40}$'
    AND interval_seconds BETWEEN 120 AND 3600
    AND isfinite(last_success_at)
    AND last_success_at<=checked_at
    AND last_success_at>=checked_at-make_interval(secs=>greatest(600,interval_seconds*3));

  SELECT value,last_verified_at INTO approval,reviewed_at
  FROM public.dufynd_master_status WHERE key='ops.render_release_expectations_v1';
  IF NOT FOUND THEN
    binding_reason := 'release_expectation_missing';
  ELSIF jsonb_typeof(approval) IS DISTINCT FROM 'object' OR length(approval::text)>20000 THEN
    binding_reason := 'release_expectation_invalid';
  ELSIF approval-ARRAY['version','repository','branch','repository_head_sha','approval_status','approved_at','valid_until','services']<>'{}'::jsonb
    OR approval->'version' IS DISTINCT FROM '1'::jsonb
    OR approval->>'repository' IS DISTINCT FROM 'tncommerce/commerce-agents'
    OR approval->>'branch' IS DISTINCT FROM 'scentai-mvp'
    OR approval->>'approval_status' IS DISTINCT FROM 'approved'
    OR jsonb_typeof(approval->'repository_head_sha') IS DISTINCT FROM 'string'
    OR coalesce(approval->>'repository_head_sha','') !~ '^[a-f0-9]{40}$'
    OR jsonb_typeof(approval->'services') IS DISTINCT FROM 'array' THEN
    binding_reason := 'release_expectation_invalid';
  ELSE
    IF jsonb_array_length(approval->'services')<>2 THEN
      binding_reason := 'release_service_coverage_invalid';
    ELSE
      FOR item IN SELECT value FROM jsonb_array_elements(approval->'services') LOOP
        IF jsonb_typeof(item) IS DISTINCT FROM 'object' THEN
          binding_reason := 'release_service_invalid';
          EXIT;
        END IF;
        IF item-ARRAY['component','service_id','expected_deployment_sha','decision','scope','evidence_ref','rationale']<>'{}'::jsonb
          OR jsonb_typeof(item->'component') IS DISTINCT FROM 'string'
          OR jsonb_typeof(item->'service_id') IS DISTINCT FROM 'string'
          OR jsonb_typeof(item->'expected_deployment_sha') IS DISTINCT FROM 'string'
          OR coalesce(item->>'expected_deployment_sha','') !~ '^[a-f0-9]{40}$'
          OR jsonb_typeof(item->'decision') IS DISTINCT FROM 'string'
          OR coalesce(item->>'decision','') NOT IN ('hold_existing_release','deploy_approved_release')
          OR jsonb_typeof(item->'scope') IS DISTINCT FROM 'string'
          OR jsonb_typeof(item->'evidence_ref') IS DISTINCT FROM 'string'
          OR length(btrim(item->>'evidence_ref')) NOT BETWEEN 1 AND 500
          OR jsonb_typeof(item->'rationale') IS DISTINCT FROM 'string'
          OR length(btrim(item->>'rationale')) NOT BETWEEN 1 AND 1000
          OR NOT coalesce(
            (item->>'component'='api' AND item->>'service_id'='srv-dakpfrnf3r2c73dr3f20' AND item->>'scope'='api_runtime')
            OR (item->>'component'='storefront' AND item->>'service_id'='srv-dakpiajl550s73cp4lvg' AND item->>'scope'='storefront_static'),false) THEN
          binding_reason := 'release_service_invalid';
          EXIT;
        END IF;
        IF approved_services ? (item->>'service_id') THEN
          binding_reason := 'release_service_duplicate';
          EXIT;
        END IF;
        approved_services := approved_services || jsonb_build_object(item->>'service_id',item);
      END LOOP;
    END IF;
    IF binding_reason IS NULL AND NOT (
      approved_services ? 'srv-dakpfrnf3r2c73dr3f20'
      AND approved_services ? 'srv-dakpiajl550s73cp4lvg') THEN
      binding_reason := 'release_service_coverage_invalid';
    END IF;
    IF binding_reason IS NULL THEN
      IF jsonb_typeof(approval->'approved_at') IS DISTINCT FROM 'string'
        OR coalesce(approval->>'approved_at','') !~ iso_timestamp
        OR (approval ? 'valid_until' AND (
          jsonb_typeof(approval->'valid_until') IS DISTINCT FROM 'string'
          OR coalesce(approval->>'valid_until','') !~ iso_timestamp)) THEN
        binding_reason := 'release_approval_time_invalid';
      ELSE
        BEGIN
          approved_at := (approval->>'approved_at')::timestamptz;
          IF approval ? 'valid_until' THEN valid_until := (approval->>'valid_until')::timestamptz; END IF;
        EXCEPTION WHEN invalid_datetime_format OR datetime_field_overflow OR invalid_time_zone_displacement_value THEN
          binding_reason := 'release_approval_time_invalid';
        END;
        IF binding_reason IS NULL THEN
          IF approved_at IS NULL OR NOT isfinite(approved_at) OR approved_at>checked_at
            OR reviewed_at IS NULL OR NOT isfinite(reviewed_at) OR reviewed_at>checked_at OR reviewed_at<approved_at
            OR (valid_until IS NOT NULL AND (NOT isfinite(valid_until) OR valid_until<approved_at)) THEN
            binding_reason := 'release_approval_time_invalid';
          ELSIF valid_until IS NOT NULL AND valid_until<=checked_at THEN
            binding_reason := 'release_approval_expired';
          END IF;
        END IF;
      END IF;
    END IF;
  END IF;
  IF binding_reason IS NULL THEN
    IF github_sha IS NULL THEN binding_reason := 'github_head_unverified';
    ELSIF approval->>'repository_head_sha' IS DISTINCT FROM github_sha THEN binding_reason := 'repository_head_changed';
    END IF;
  END IF;

  -- The service inventory is explicit even when an observer is missing. An
  -- additional enabled Render identity cannot silently inherit either approval.
  FOR target IN
    SELECT 'api'::text AS component,'srv-dakpfrnf3r2c73dr3f20'::text AS service_id
    UNION ALL SELECT 'storefront','srv-dakpiajl550s73cp4lvg'
    UNION ALL SELECT 'unregistered',source_id
      FROM public.dufynd_external_observers WHERE enabled AND source_type='render'
        AND (source_id IS NULL OR source_id NOT IN ('srv-dakpfrnf3r2c73dr3f20','srv-dakpiajl550s73cp4lvg'))
      GROUP BY source_id
  LOOP
    item := CASE WHEN binding_reason IS NULL THEN approved_services->target.service_id ELSE NULL END;
    observer := NULL;
    observed_sha := NULL;
    source_valid := false;
    snapshot_valid := false;
    observation_verified := false;
    observation_reason := NULL;
    intent_match := NULL;
    IF target.component='unregistered' THEN extra_count := extra_count+1; END IF;
    SELECT count(*)::integer INTO observer_count FROM public.dufynd_external_observers
      WHERE source_type='render' AND source_id IS NOT DISTINCT FROM target.service_id;
    IF observer_count=0 THEN
      observation_reason := 'observer_missing';
      missing_count := missing_count+1;
    ELSIF observer_count<>1 THEN
      observation_reason := 'observer_ambiguous';
    ELSE
      SELECT * INTO observer FROM public.dufynd_external_observers
        WHERE source_type='render' AND source_id IS NOT DISTINCT FROM target.service_id;
      source_valid := coalesce(observer.observer_id='render:'||target.service_id
        AND observer.source_type='render' AND observer.source_id=target.service_id,false);
      snapshot_valid := source_valid
        AND jsonb_typeof(observer.last_snapshot)='object'
        AND jsonb_typeof(observer.last_snapshot->'service_id')='string'
        AND observer.last_snapshot->>'service_id'=target.service_id
        AND jsonb_typeof(observer.last_snapshot->'sha')='string'
        AND observer.last_snapshot->>'sha' ~ '^[a-f0-9]{40}$';
      snapshot_valid := coalesce(snapshot_valid,false);
      IF jsonb_typeof(observer.last_snapshot->'sha')='string'
        AND observer.last_snapshot->>'sha' ~ '^[a-f0-9]{40}$' THEN
        observed_sha := observer.last_snapshot->>'sha';
      END IF;
      IF observer.enabled IS DISTINCT FROM true THEN
        observation_reason := 'observer_disabled';
        missing_count := missing_count+1;
      ELSIF NOT source_valid THEN observation_reason := 'observer_identity_invalid';
      ELSIF NOT snapshot_valid THEN observation_reason := 'deployment_identity_invalid';
      ELSIF observer.last_snapshot->>'state' IS DISTINCT FROM 'live'
        OR jsonb_typeof(observer.last_snapshot->'deployment_id') IS DISTINCT FROM 'string'
        OR coalesce(observer.last_snapshot->>'deployment_id','') !~ '^dep-[a-z0-9]+$' THEN
        observation_reason := 'live_deployment_unverified';
      ELSIF observer.health_status IS DISTINCT FROM 'healthy' THEN observation_reason := 'observer_unhealthy';
      ELSIF observer.last_success_at IS NULL OR NOT isfinite(observer.last_success_at)
        OR observer.last_success_at>checked_at OR observer.interval_seconds IS NULL
        OR observer.interval_seconds NOT BETWEEN 120 AND 3600
        OR observer.last_success_at<checked_at-make_interval(secs=>greatest(600,observer.interval_seconds*3)) THEN
        observation_reason := 'observer_success_unverified';
      ELSE observation_verified := true;
      END IF;
      IF item IS NOT NULL AND snapshot_valid THEN intent_match := observed_sha=item->>'expected_deployment_sha'; END IF;
    END IF;
    IF NOT observation_verified THEN unverified_count := unverified_count+1; END IF;
    comparison_status := CASE
      WHEN item IS NULL OR intent_match IS NULL OR NOT observation_verified THEN 'unknown'
      WHEN intent_match THEN 'aligned' ELSE 'mismatch' END;
    IF comparison_status='unknown' THEN unknown_count := unknown_count+1;
    ELSIF comparison_status='mismatch' THEN mismatch_count := mismatch_count+1;
    END IF;
    services := services || jsonb_build_array(jsonb_build_object(
      'component',target.component,'service_id',target.service_id,
      'expectation_status',CASE WHEN item IS NULL THEN 'unknown' ELSE 'approved' END,
      'expectation_reason',CASE WHEN item IS NULL THEN coalesce(binding_reason,'service_release_unapproved') ELSE NULL END,
      'expected_deployment_sha',item->>'expected_deployment_sha','decision',item->>'decision',
      'scope',item->>'scope','evidence_ref',item->>'evidence_ref','rationale',item->>'rationale',
      'observer_id',observer.observer_id,'health_status',observer.health_status,
      'last_success_at',observer.last_success_at,'observed_deployment_sha',observed_sha,
      'observed_state',observer.last_snapshot->>'state','deployment_id',observer.last_snapshot->>'deployment_id',
      'intent_match',intent_match,'observation_verified',observation_verified,
      'observation_reason',observation_reason,'comparison_status',comparison_status));
  END LOOP;
  IF binding_reason IS NOT NULL OR extra_count>0 THEN issues := issues || '"render_release_expectation_unknown"'::jsonb; END IF;
  IF missing_count>0 THEN issues := issues || '"render_monitor_missing"'::jsonb; END IF;
  IF unverified_count>0 THEN issues := issues || '"render_release_observation_unverified"'::jsonb; END IF;
  IF mismatch_count>0 THEN issues := issues || '"render_release_mismatch"'::jsonb; END IF;
  RETURN jsonb_build_object(
    'version',1,'observed_at',checked_at,'contract_key','ops.render_release_expectations_v1',
    'repository_head_sha',github_sha,'github_observed_at',github_observed_at,
    'binding_status',CASE WHEN binding_reason IS NULL THEN 'approved' ELSE 'unknown' END,
    'binding_reason',binding_reason,'approved_at',approved_at,'valid_until',valid_until,
    'last_verified_at',reviewed_at,'services',services,'expected_service_count',2,
    'additional_service_count',extra_count,'missing_monitor_count',missing_count,
    'unverified_observation_count',unverified_count,'unknown_service_count',unknown_count,
    'revision_mismatch_count',mismatch_count,
    'status',CASE WHEN mismatch_count>0 THEN 'mismatch' WHEN unknown_count>0 THEN 'unknown' ELSE 'verified' END,
    'technical_work_remaining',unknown_count>0 OR mismatch_count>0,'issues',issues,
    'code_equivalence_verified',false,'diagnostic_only',true,'new_spend_usd',0);
END;
$function$;

REVOKE ALL ON FUNCTION public.read_dufynd_render_release_expectations_v1() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.read_dufynd_render_release_expectations_v1() TO service_role,postgres;

-- Preserve the existing technical classifier; only service-revision evidence
-- is delegated. Private freshness, broker source binding and public health stay.
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
    'diagnostic_only',true,'technical_repair_executed',false,'new_spend_usd',0
  );
end;
$function$;

-- Preserve the existing security-definer audit and its masterstatus projection.
-- Both consumers use exactly the same approval/provider classification.
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
  private_broker_scheduler_gap boolean := false;
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
  if private_broker_scheduler_gap then issues := issues || '"private_broker_scheduler_gap"'::jsonb; end if;
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
    'private_broker_scheduler_gap',private_broker_scheduler_gap,
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
