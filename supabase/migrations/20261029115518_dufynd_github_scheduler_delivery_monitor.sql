-- Independent observation of GitHub's public, natural scheduler deliveries.
-- No dispatch, credential, provider capture, task creation or new cron. Disabled
-- until an explicitly authorized metadata activation. The existing supervisor
-- can call the poller; the integration is a separate forward migration.
INSERT INTO public.dufynd_master_status(key,category,value,priority,last_verified_at)
VALUES ('ops.github_scheduler_delivery_v1','operations',jsonb_build_object(
  'version',1,'enabled',false,'scope','public_github_schedule_delivery_only',
  'repository','tncommerce/commerce-agents','branch','main',
  'budget',jsonb_build_object('next_target','reader','last_attempt_at',null,
    'next_poll_at',clock_timestamp(),'blocked',false),
  'schedules',jsonb_build_object('reader',jsonb_build_object('transport_status','unknown'),
    'watchdog',jsonb_build_object('transport_status','unknown'))
),90,clock_timestamp()) ON CONFLICT(key) DO NOTHING;

CREATE OR REPLACE FUNCTION public.dufynd_scheduler_parse_time_v1(p_value jsonb)
RETURNS timestamptz LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER
SET search_path TO pg_catalog,public
AS $parse_time$
DECLARE parsed timestamptz;
BEGIN
  IF jsonb_typeof(p_value) IS DISTINCT FROM 'string' OR
     (p_value#>>'{}') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?(Z|[+-][0-9]{2}:[0-9]{2})$' THEN
    RETURN null;
  END IF;
  BEGIN parsed:=(p_value#>>'{}')::timestamptz;
  EXCEPTION WHEN invalid_datetime_format OR datetime_field_overflow OR SQLSTATE '22009' THEN
    RETURN null;
  END;
  IF NOT isfinite(parsed) THEN RETURN null; END IF;
  RETURN parsed;
END
$parse_time$;

CREATE OR REPLACE FUNCTION public.normalize_dufynd_github_scheduler_run_v1(
  p_target text,p_body jsonb,p_receipt_at timestamptz)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER
SET search_path TO pg_catalog,public
AS $normalize_run$
DECLARE
  workflow_id bigint; workflow_path text; run jsonb; repo jsonb; head_repo jsonb;
  created_at timestamptz; started_at timestamptz; updated_at timestamptz;
  total_count integer; attempt integer; normalized jsonb;
BEGIN
  IF p_target='reader' THEN
    workflow_id:=373752411; workflow_path:='.github/workflows/dufynd-private-observer.yml';
  ELSIF p_target='watchdog' THEN
    workflow_id:=377395476; workflow_path:='.github/workflows/dufynd-private-observer-watchdog.yml';
  ELSE RETURN jsonb_build_object('valid',false,'error','target_rejected'); END IF;
  IF p_receipt_at IS NULL OR NOT isfinite(p_receipt_at)
     OR jsonb_typeof(p_body) IS DISTINCT FROM 'object'
     OR jsonb_typeof(p_body->'workflow_runs') IS DISTINCT FROM 'array'
     OR jsonb_typeof(p_body->'total_count') IS DISTINCT FROM 'number'
     OR coalesce(p_body->>'total_count','') !~ '^[0-9]{1,9}$' THEN
    RETURN jsonb_build_object('valid',false,'error','run_list_rejected');
  END IF;
  total_count:=(p_body->>'total_count')::integer;
  IF jsonb_array_length(p_body->'workflow_runs')>1
     OR (total_count=0) IS DISTINCT FROM (jsonb_array_length(p_body->'workflow_runs')=0) THEN
    RETURN jsonb_build_object('valid',false,'error','run_list_rejected');
  END IF;
  IF total_count=0 THEN
    RETURN jsonb_build_object('valid',true,'snapshot',jsonb_build_object(
      'total_count',0,'workflow_runs','[]'::jsonb));
  END IF;
  run:=p_body->'workflow_runs'->0; repo:=run->'repository'; head_repo:=run->'head_repository';
  IF jsonb_typeof(run) IS DISTINCT FROM 'object'
     OR jsonb_typeof(run->'id') IS DISTINCT FROM 'number'
     OR coalesce(run->>'id','') !~ '^[1-9][0-9]{0,17}$'
     OR run->'workflow_id' IS DISTINCT FROM to_jsonb(workflow_id)
     OR run->>'path' IS DISTINCT FROM workflow_path
     OR run->>'head_branch' IS DISTINCT FROM 'main'
     OR run->>'event' IS DISTINCT FROM 'schedule'
     OR jsonb_typeof(run->'head_sha') IS DISTINCT FROM 'string'
     OR coalesce(run->>'head_sha','') !~ '^[0-9a-f]{40}$'
     OR jsonb_typeof(repo) IS DISTINCT FROM 'object'
     OR repo->'id' IS DISTINCT FROM '1367576041'::jsonb
     OR repo->>'full_name' IS DISTINCT FROM 'tncommerce/commerce-agents'
     OR repo->>'name' IS DISTINCT FROM 'commerce-agents'
     OR repo->'owner'->'id' IS DISTINCT FROM '324597697'::jsonb
     OR repo->'owner'->>'login' IS DISTINCT FROM 'tncommerce'
     OR repo->'private' IS DISTINCT FROM 'false'::jsonb
     OR jsonb_typeof(head_repo) IS DISTINCT FROM 'object'
     OR head_repo->'id' IS DISTINCT FROM '1367576041'::jsonb
     OR head_repo->>'full_name' IS DISTINCT FROM 'tncommerce/commerce-agents'
     OR head_repo->>'name' IS DISTINCT FROM 'commerce-agents'
     OR head_repo->'owner'->'id' IS DISTINCT FROM '324597697'::jsonb
     OR head_repo->'owner'->>'login' IS DISTINCT FROM 'tncommerce'
     OR head_repo->'private' IS DISTINCT FROM 'false'::jsonb
     OR jsonb_typeof(run->'run_attempt') IS DISTINCT FROM 'number'
     OR coalesce(run->>'run_attempt','') !~ '^[1-9][0-9]{0,5}$' THEN
    RETURN jsonb_build_object('valid',false,'error','run_identity_rejected');
  END IF;
  attempt:=(run->>'run_attempt')::integer;
  created_at:=public.dufynd_scheduler_parse_time_v1(run->'created_at');
  started_at:=public.dufynd_scheduler_parse_time_v1(run->'run_started_at');
  updated_at:=public.dufynd_scheduler_parse_time_v1(run->'updated_at');
  IF created_at IS NULL OR created_at>p_receipt_at OR updated_at IS NULL
     OR updated_at<created_at OR updated_at>p_receipt_at
     OR NOT run ? 'run_started_at'
     OR (run->'run_started_at'<>'null'::jsonb AND started_at IS NULL)
     OR started_at<created_at OR started_at>p_receipt_at
     OR (run->>'status' IN ('completed','in_progress') AND started_at IS NULL) THEN
    RETURN jsonb_build_object('valid',false,'error','run_time_rejected');
  END IF;
  IF coalesce(run->>'status','') NOT IN ('completed','in_progress','queued','requested','waiting','pending')
     OR NOT run ? 'conclusion'
     OR (run->>'status'='completed' AND coalesce(run->>'conclusion','') NOT IN
       ('success','failure','neutral','cancelled','skipped','timed_out','action_required','stale','startup_failure'))
     OR (run->>'status'<>'completed' AND run->'conclusion' IS DISTINCT FROM 'null'::jsonb) THEN
    RETURN jsonb_build_object('valid',false,'error','run_result_rejected');
  END IF;
  repo:=jsonb_build_object('id',1367576041,'full_name','tncommerce/commerce-agents','name','commerce-agents',
    'owner',jsonb_build_object('id',324597697,'login','tncommerce'),'private',false);
  normalized:=jsonb_build_object('id',(run->>'id')::bigint,'workflow_id',workflow_id,
    'path',workflow_path,'repository',repo,'head_repository',repo,'head_branch','main',
    'event','schedule','head_sha',run->>'head_sha',
    'created_at',to_char(created_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'run_started_at',to_char(started_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'updated_at',to_char(updated_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),'run_attempt',attempt,
    'status',run->>'status','conclusion',run->'conclusion');
  RETURN jsonb_build_object('valid',true,'snapshot',jsonb_build_object(
    'total_count',total_count,'workflow_runs',jsonb_build_array(normalized)));
END
$normalize_run$;

CREATE OR REPLACE FUNCTION public.read_dufynd_github_scheduler_delivery_v1()
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY INVOKER
SET search_path TO pg_catalog,public
AS $scheduler_read$
DECLARE
  s jsonb; t jsonb; budget jsonb; result jsonb; schedules jsonb:='{}'; issues jsonb:='[]';
  target text; normalized jsonb; run jsonb; item jsonb; reason text;
  checked_at timestamptz; observed_at timestamptz;
  requested_at timestamptz; pending_at timestamptz; natural_at timestamptz;
  last_attempt_at timestamptz; next_poll_at timestamptz; oldest_receipt_at timestamptz;
  latest_natural_at timestamptz; transport text; delivery text; dispatch text;
  fresh_count integer:=0; stale_count integer:=0; delivered_count integer:=0;
  failed_count integer:=0; success_count integer:=0; pending_count integer:=0;
  enabled boolean; budget_valid boolean; status text; delivery_status text;
BEGIN
  SELECT value INTO s FROM public.dufynd_master_status WHERE key='ops.github_scheduler_delivery_v1';
  -- A caller may already have waited on its own planner/audit lock. Use the
  -- actual read time, not the start of that older calling SQL statement.
  checked_at:=clock_timestamp();
  IF jsonb_typeof(s) IS DISTINCT FROM 'object' THEN s:='{}'; END IF;
  enabled:=s->'enabled' IS NOT DISTINCT FROM 'true'::jsonb;
  result:=jsonb_build_object('version',1,'enabled',enabled,'healthy',false,
    'scope','public_github_schedule_delivery_only','repository','tncommerce/commerce-agents',
    'branch','main','checked_at',checked_at,'interval_seconds',600,'freshness_seconds',1200,
    'delivery_threshold_seconds',1500,'private_observer_evidence',false,'full_chain_complete',false,
    'business_success',false,'capture_verified',false,'cadence_guarantee',false,
    'delivery_window_scope','latest_natural_creation_within_25_minutes',
    'dispatch_status_basis','github_workflow_run_conclusion','downstream_dispatch_verified',false,
    'redirect_chain_verified',false,
    'final_origin_verified',false,'redirect_behavior','pg_net_follows_redirects');
  budget:=s->'budget';
  last_attempt_at:=public.dufynd_scheduler_parse_time_v1(budget->'last_attempt_at');
  next_poll_at:=public.dufynd_scheduler_parse_time_v1(budget->'next_poll_at');
  budget_valid:=jsonb_typeof(budget) IS NOT DISTINCT FROM 'object'
    AND budget->'blocked' IS NOT DISTINCT FROM 'false'::jsonb
    AND coalesce(budget->>'next_target','') IN ('reader','watchdog')
    AND budget ? 'last_attempt_at' AND next_poll_at IS NOT NULL
    AND ((budget->'last_attempt_at'='null'::jsonb AND budget->>'next_target'='reader')
      OR (last_attempt_at IS NOT NULL AND last_attempt_at<=checked_at
        AND next_poll_at>=last_attempt_at+interval '300 seconds'));
  FOREACH target IN ARRAY ARRAY['reader','watchdog'] LOOP
    t:=s->'schedules'->target; transport:='unknown'; delivery:='unknown'; dispatch:='unknown';
    reason:=null; run:=null; natural_at:=null;
    observed_at:=public.dufynd_scheduler_parse_time_v1(t->'observed_at');
    requested_at:=public.dufynd_scheduler_parse_time_v1(t->'receipt_requested_at');
    pending_at:=public.dufynd_scheduler_parse_time_v1(t->'requested_at');
    IF NOT enabled THEN reason:='monitor_disabled';
    ELSIF NOT coalesce(budget_valid,false) OR s->>'last_error' IS NOT NULL THEN reason:='monitor_state_unavailable';
    ELSIF jsonb_typeof(t) IS DISTINCT FROM 'object' THEN reason:='schedule_state_unavailable';
    ELSIF t ? 'request_id' AND (jsonb_typeof(t->'request_id') IS DISTINCT FROM 'number'
      OR coalesce(t->>'request_id','') !~ '^[1-9][0-9]{0,17}$'
      OR pending_at IS NULL OR pending_at>checked_at OR pending_at<checked_at-interval '180 seconds') THEN
      reason:='request_overdue_or_invalid';
    ELSIF t->>'transport_status' IS DISTINCT FROM 'observed' THEN reason:=coalesce(t->>'last_error','observation_unavailable');
    ELSIF observed_at IS NULL OR requested_at IS NULL OR observed_at<requested_at
      OR observed_at>checked_at OR t->'status_code' IS DISTINCT FROM '200'::jsonb
      OR jsonb_typeof(t->'receipt_id') IS DISTINCT FROM 'number'
      OR coalesce(t->>'receipt_id','') !~ '^[1-9][0-9]{0,17}$'
      OR jsonb_typeof(t->'response_bytes') IS DISTINCT FROM 'number'
      OR coalesce(t->>'response_bytes','') !~ '^[1-9][0-9]{0,4}$'
      OR t->>'response_contract' IS DISTINCT FROM 'github_schedule_runs_v1' THEN
      reason:='observation_provenance_invalid';
    ELSIF (t->>'response_bytes')::integer>65536 THEN reason:='observation_provenance_invalid';
    ELSE
      normalized:=public.normalize_dufynd_github_scheduler_run_v1(target,t->'snapshot',observed_at);
      IF normalized->'valid' IS DISTINCT FROM 'true'::jsonb THEN reason:='observation_payload_invalid';
      ELSE
        run:=normalized->'snapshot'->'workflow_runs'->0;
        natural_at:=public.dufynd_scheduler_parse_time_v1(run->'created_at');
        oldest_receipt_at:=least(oldest_receipt_at,observed_at);
        latest_natural_at:=greatest(latest_natural_at,natural_at);
        IF observed_at<checked_at-interval '1200 seconds' THEN
          transport:='stale'; reason:='observation_stale'; stale_count:=stale_count+1;
        ELSE
          transport:='fresh'; fresh_count:=fresh_count+1;
          IF natural_at IS NULL OR natural_at<checked_at-interval '1500 seconds' THEN delivery:='gap';
          ELSE delivery:='available'; delivered_count:=delivered_count+1; END IF;
          -- Rerunning an old scheduled run neither delivers a new natural event
          -- nor proves that the ORIGINAL scheduler dispatch succeeded.
          IF run->'run_attempt'='1'::jsonb THEN
            IF run->>'status'='completed' THEN
              IF run->>'conclusion'='success' THEN dispatch:='success'; success_count:=success_count+1;
              ELSE dispatch:='failed'; failed_count:=failed_count+1; END IF;
            ELSE dispatch:='pending'; pending_count:=pending_count+1; END IF;
          END IF;
        END IF;
      END IF;
    END IF;
    item:=jsonb_build_object('workflow_id',CASE target WHEN 'reader' THEN 373752411 ELSE 377395476 END,
      'workflow_path',CASE target WHEN 'reader' THEN '.github/workflows/dufynd-private-observer.yml'
        ELSE '.github/workflows/dufynd-private-observer-watchdog.yml' END,
      'transport_status',transport,'delivery_status',delivery,'dispatch_status',dispatch,
      'observed_at',observed_at,'latest_natural_created_at',natural_at,
      'latest_attempt_started_at',run->'run_started_at','natural_run',run,
      'request_pending',coalesce(t ? 'request_id',false),'last_attempt_at',t->'last_attempt_at',
      'last_error',t->'last_error','reason',reason);
    schedules:=schedules||jsonb_build_object(target,item);
  END LOOP;
  IF NOT enabled THEN status:='disabled'; delivery_status:='unknown';
  ELSIF fresh_count=0 THEN status:=CASE WHEN stale_count>0 THEN 'stale' ELSE 'unknown' END; delivery_status:='unknown';
  ELSIF fresh_count=2 AND delivered_count=0 THEN status:='gap'; delivery_status:='gap';
  ELSIF delivered_count=2 THEN delivery_status:='available';
    status:=CASE WHEN success_count=2 THEN 'healthy' ELSE 'degraded' END;
  ELSIF delivered_count=1 THEN status:='degraded'; delivery_status:='degraded';
  ELSE status:='unknown'; delivery_status:='unknown'; END IF;
  IF fresh_count<2 THEN
    IF stale_count>0 THEN issues:=issues||'"github_scheduler_observation_stale"'::jsonb; END IF;
    IF fresh_count+stale_count<2 THEN issues:=issues||'"github_scheduler_observation_unavailable"'::jsonb; END IF;
  END IF;
  IF delivery_status='gap' THEN issues:=issues||'"github_scheduler_delivery_gap"'::jsonb;
  ELSIF delivery_status='degraded' THEN issues:=issues||'"github_scheduler_delivery_degraded"'::jsonb; END IF;
  IF failed_count>0 THEN issues:=issues||'"github_scheduler_dispatch_failed"'::jsonb;
  ELSIF fresh_count>0 AND success_count<fresh_count THEN issues:=issues||'"github_scheduler_dispatch_unverified"'::jsonb; END IF;
  RETURN result||jsonb_build_object('status',status,'healthy',status='healthy',
    'transport_status',CASE WHEN fresh_count=2 THEN 'fresh' WHEN fresh_count=1 THEN 'partial'
      WHEN stale_count>0 THEN 'stale' ELSE 'unknown' END,
    'delivery_status',delivery_status,'delivery_gap',CASE WHEN fresh_count=2 THEN delivered_count=0 ELSE null END,
    'dispatch_status',CASE WHEN failed_count>0 THEN 'failed' WHEN success_count=2 THEN 'success'
      WHEN pending_count>0 THEN 'pending' ELSE 'unknown' END,
    'observed_at',oldest_receipt_at,'latest_natural_created_at',latest_natural_at,
    'schedules',schedules,'issues',issues,'next_poll_at',next_poll_at,
    'budget_blocked',budget->'blocked' IS DISTINCT FROM 'false'::jsonb,
    'budget_block_reason',budget->'block_reason');
END
$scheduler_read$;

CREATE OR REPLACE FUNCTION public.poll_dufynd_github_scheduler_delivery_v1()
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER
SET search_path TO pg_catalog,public
AS $scheduler_poll$
DECLARE
  s jsonb; budget jsonb; t jsonb; normalized jsonb; body jsonb; old_run jsonb; new_run jsonb;
  target text; candidate text; endpoint text; workflow_id bigint; response record;
  checked_at timestamptz; requested_at timestamptz; last_attempt_at timestamptz;
  next_poll_at timestamptz; target_attempt_at timestamptz; retry_at timestamptz;
  request_id bigint; response_count integer; queued boolean;
  failure text; failures integer; delay_seconds integer; header text; raw_header jsonb;
  header_count integer; limit_invalid boolean; rate_limited boolean; n bigint;
BEGIN
  IF NOT pg_try_advisory_xact_lock(hashtext('dufynd-github-scheduler-delivery-v1')) THEN
    RETURN public.read_dufynd_github_scheduler_delivery_v1()||jsonb_build_object('poll_busy',true);
  END IF;
  SELECT value INTO s FROM public.dufynd_master_status
  WHERE key='ops.github_scheduler_delivery_v1' FOR UPDATE;
  checked_at:=clock_timestamp();
  IF jsonb_typeof(s) IS DISTINCT FROM 'object' OR s->'enabled' IS DISTINCT FROM 'true'::jsonb THEN
    RETURN public.read_dufynd_github_scheduler_delivery_v1();
  END IF;
  budget:=s->'budget';
  last_attempt_at:=public.dufynd_scheduler_parse_time_v1(budget->'last_attempt_at');
  next_poll_at:=public.dufynd_scheduler_parse_time_v1(budget->'next_poll_at');
  -- Never reset a missing, malformed or future budget to "due now". A single
  -- global 300s gate plus per-target 600s gates bounds even repeated errors.
  IF jsonb_typeof(budget) IS DISTINCT FROM 'object'
    OR budget->'blocked' IS DISTINCT FROM 'false'::jsonb
    OR coalesce(budget->>'next_target','') NOT IN ('reader','watchdog')
    OR NOT budget ? 'last_attempt_at' OR next_poll_at IS NULL
    OR (budget->'last_attempt_at'<>'null'::jsonb AND (last_attempt_at IS NULL
      OR last_attempt_at>checked_at OR next_poll_at<last_attempt_at+interval '300 seconds'))
    OR (budget->'last_attempt_at'='null'::jsonb AND budget->>'next_target'<>'reader')
    OR jsonb_typeof(s->'schedules') IS DISTINCT FROM 'object'
    OR jsonb_typeof(s->'schedules'->'reader') IS DISTINCT FROM 'object'
    OR jsonb_typeof(s->'schedules'->'watchdog') IS DISTINCT FROM 'object'
    OR (s->'schedules')-ARRAY['reader','watchdog']<>'{}'::jsonb THEN
    s:=s||jsonb_build_object('last_error',CASE WHEN budget->'blocked'='true'::jsonb
      THEN 'transport_budget_held' ELSE 'monitor_budget_invalid' END,'last_error_at',checked_at);
    UPDATE public.dufynd_master_status SET value=s,last_verified_at=checked_at
    WHERE key='ops.github_scheduler_delivery_v1';
    RETURN public.read_dufynd_github_scheduler_delivery_v1();
  END IF;
  IF budget->'last_attempt_at'='null'::jsonb AND EXISTS(
    SELECT 1 FROM jsonb_each(s->'schedules') e WHERE e.value ?| ARRAY['request_id','last_attempt_at','receipt_id']) THEN
    s:=s||jsonb_build_object('last_error','monitor_budget_invalid','last_error_at',checked_at);
  ELSIF to_regnamespace('net') IS NULL OR to_regclass('net._http_response') IS NULL
    OR to_regclass('net.http_request_queue') IS NULL THEN
    s:=s||jsonb_build_object('last_error','pg_net_unavailable','last_error_at',checked_at);
  ELSE
    s:=s-'last_error';
    FOREACH target IN ARRAY ARRAY['reader','watchdog'] LOOP
      t:=s->'schedules'->target; failure:=null;
      IF NOT t ? 'request_id' THEN CONTINUE; END IF;
      requested_at:=public.dufynd_scheduler_parse_time_v1(t->'requested_at');
      workflow_id:=CASE target WHEN 'reader' THEN 373752411 ELSE 377395476 END;
      IF jsonb_typeof(t->'request_id') IS DISTINCT FROM 'number'
        OR coalesce(t->>'request_id','') !~ '^[1-9][0-9]{0,17}$'
        OR requested_at IS NULL OR requested_at>checked_at
        OR t->'request_workflow_id' IS DISTINCT FROM to_jsonb(workflow_id)
        OR (t ? 'last_consumed_request_id' AND (jsonb_typeof(t->'last_consumed_request_id') IS DISTINCT FROM 'number'
          OR coalesce(t->>'last_consumed_request_id','') !~ '^[1-9][0-9]{0,17}$')) THEN
        t:=t||jsonb_build_object('transport_status','error','last_error','invalid_pending_state');
        s:=jsonb_set(s,ARRAY['schedules',target],t); CONTINUE;
      END IF;
      request_id:=(t->>'request_id')::bigint;
      IF request_id<=coalesce((t->>'last_consumed_request_id')::bigint,0) THEN
        t:=t||jsonb_build_object('transport_status','error','last_error','replayed_receipt_identity');
        s:=jsonb_set(s,ARRAY['schedules',target],t); CONTINUE;
      END IF;
      EXECUTE 'select *,count(*) over () as receipt_count from (
          select status_code,content_type,created,timed_out,error_msg is not null as has_error,
            octet_length(content) as body_bytes,
            case when octet_length(content)<=65536 then content else null end as content,
            case when octet_length(headers::text)<=8192 then headers else null end as headers
          from net._http_response where id=$1 limit 2) receipts limit 1'
        INTO response USING request_id;
      response_count:=coalesce(response.receipt_count,0); checked_at:=clock_timestamp();
      IF response_count=0 THEN
        IF requested_at>=checked_at-interval '60 seconds' THEN CONTINUE; END IF;
        EXECUTE 'select exists(select 1 from net.http_request_queue where id=$1)' INTO queued USING request_id;
        IF queued THEN
          t:=t||jsonb_build_object('transport_status','error','last_error','request_dispatch_overdue',
            'last_error_at',checked_at);
          s:=jsonb_set(s,ARRAY['schedules',target],t); CONTINUE;
        END IF;
        failure:='response_missing';
      ELSIF response_count<>1 THEN failure:='ambiguous_scheduler_receipt';
      ELSIF response.timed_out IS TRUE THEN failure:='transport_timeout';
      ELSIF response.has_error THEN failure:='transport_failure';
      ELSIF response.created IS NULL OR NOT isfinite(response.created)
        OR response.created<requested_at OR response.created>checked_at
        OR response.created<checked_at-interval '1200 seconds' THEN failure:='response_not_fresh';
      ELSIF jsonb_typeof(response.headers) IS DISTINCT FROM 'object' THEN failure:='response_headers_rejected';
      ELSIF EXISTS(SELECT 1 FROM jsonb_object_keys(response.headers) h WHERE lower(h)='location') THEN
        failure:='redirect_response_unverified';
      ELSE
        -- Rate headers affect the GLOBAL budget, including an exhausted quota
        -- reported on a successful response. Never truncate a provider wait.
        retry_at:=null; limit_invalid:=false;
        rate_limited:=response.status_code IN (403,429);
        FOREACH header IN ARRAY ARRAY['retry-after','x-ratelimit-remaining','x-ratelimit-reset','x-poll-interval'] LOOP
          SELECT count(*),(array_agg(value))[1] INTO header_count,raw_header
          FROM jsonb_each(response.headers) WHERE lower(key)=header;
          IF header_count=0 THEN CONTINUE; END IF;
          IF header_count<>1 OR jsonb_typeof(raw_header) IS DISTINCT FROM 'string'
            OR coalesce(raw_header#>>'{}','') !~ '^[0-9]{1,12}$' THEN
            limit_invalid:=true; EXIT;
          END IF;
          n:=(raw_header#>>'{}')::bigint;
          IF header IN ('retry-after','x-poll-interval') THEN
            IF n>31536000 THEN limit_invalid:=true; EXIT; END IF;
            retry_at:=greatest(retry_at,checked_at+make_interval(secs=>n::double precision));
          ELSIF header='x-ratelimit-remaining' AND n=0 THEN rate_limited:=true;
          ELSIF header='x-ratelimit-reset' THEN
            IF n>253402214400 THEN limit_invalid:=true; EXIT; END IF;
          END IF;
        END LOOP;
        IF rate_limited AND NOT limit_invalid AND response.headers ? 'x-ratelimit-reset' THEN
          retry_at:=greatest(retry_at,to_timestamp((response.headers->>'x-ratelimit-reset')::double precision));
        ELSIF rate_limited AND NOT limit_invalid THEN
          SELECT value INTO raw_header FROM jsonb_each(response.headers) WHERE lower(key)='x-ratelimit-reset' LIMIT 1;
          IF raw_header IS NOT NULL AND NOT limit_invalid THEN
            retry_at:=greatest(retry_at,to_timestamp((raw_header#>>'{}')::double precision));
          END IF;
        END IF;
        IF rate_limited THEN retry_at:=greatest(retry_at,checked_at+interval '600 seconds'); END IF;
        IF limit_invalid THEN
          failure:='rate_limit_metadata_invalid'; budget:=budget||jsonb_build_object('blocked',true,
            'block_reason','rate_limit_metadata_invalid');
        ELSE
          next_poll_at:=greatest(next_poll_at,retry_at);
          IF response.status_code<>200 OR response.status_code IS NULL THEN
            failure:=CASE WHEN rate_limited THEN 'github_rate_limited'
              WHEN response.status_code BETWEEN 300 AND 399 THEN 'redirect_response_unverified'
              ELSE 'http_status_rejected' END;
          ELSIF btrim(split_part(lower(coalesce(response.content_type,'')),';',1))<>'application/json' THEN
            failure:='content_type_rejected';
          ELSIF response.body_bytes IS NULL OR response.body_bytes NOT BETWEEN 1 AND 65536 THEN
            failure:='response_size_rejected';
          ELSE
            BEGIN body:=response.content::jsonb;
            EXCEPTION WHEN OTHERS THEN body:=null; END;
            normalized:=public.normalize_dufynd_github_scheduler_run_v1(target,body,response.created);
            IF normalized->'valid' IS DISTINCT FROM 'true'::jsonb THEN failure:=normalized->>'error';
            ELSE
              old_run:=null;
              IF t ? 'snapshot' THEN
                body:=public.normalize_dufynd_github_scheduler_run_v1(target,t->'snapshot',
                  public.dufynd_scheduler_parse_time_v1(t->'observed_at'));
                IF body->'valid' IS DISTINCT FROM 'true'::jsonb THEN failure:='previous_evidence_invalid';
                ELSE old_run:=body->'snapshot'->'workflow_runs'->0; END IF;
              END IF;
              new_run:=normalized->'snapshot'->'workflow_runs'->0;
              IF old_run IS NOT NULL AND (new_run IS NULL
                OR public.dufynd_scheduler_parse_time_v1(new_run->'created_at')<public.dufynd_scheduler_parse_time_v1(old_run->'created_at')
                OR (new_run->'id'=old_run->'id' AND new_run->'created_at' IS DISTINCT FROM old_run->'created_at')
                OR (new_run->>'id')::bigint<(old_run->>'id')::bigint
                OR (new_run->'id'=old_run->'id' AND (new_run->>'run_attempt')::integer<(old_run->>'run_attempt')::integer)) THEN
                failure:='natural_run_history_conflict';
              ELSIF failure IS NULL THEN
                t:=t||jsonb_build_object('transport_status','observed','observed_at',response.created,
                  'receipt_requested_at',requested_at,'receipt_id',request_id,'status_code',200,
                  'response_bytes',response.body_bytes,'response_contract','github_schedule_runs_v1',
                  'snapshot',normalized->'snapshot','last_error',null,'consecutive_failures',0);
              END IF;
            END IF;
          END IF;
        END IF;
      END IF;
      -- A rejected receipt must not silently shorten an unknowable provider
      -- wait. Ambiguous rows never choose an arbitrary 200 over a hidden 429.
      -- Hold this monitor's budget; do not mutate the shared pg_net queue/config.
      IF response_count>1 THEN
        budget:=budget||jsonb_build_object('blocked',true,'block_reason','ambiguous_receipt_rate_limit_unknown');
      ELSIF response_count=1 AND failure IN ('transport_timeout','transport_failure',
        'response_not_fresh','response_headers_rejected','redirect_response_unverified') THEN
        IF response.status_code IN (403,429) OR jsonb_typeof(response.headers) IS DISTINCT FROM 'object' THEN
          budget:=budget||jsonb_build_object('blocked',true,'block_reason','rejected_receipt_rate_limit_unknown');
        ELSIF EXISTS(SELECT 1 FROM jsonb_each(response.headers) h
          WHERE lower(h.key) IN ('retry-after','x-poll-interval')
            OR (lower(h.key)='x-ratelimit-remaining' AND (jsonb_typeof(h.value) IS DISTINCT FROM 'string'
              OR coalesce(h.value#>>'{}','') !~ '^[1-9][0-9]*$'))) THEN
          budget:=budget||jsonb_build_object('blocked',true,'block_reason','rejected_receipt_rate_limit_unknown');
        END IF;
      END IF;
      t:=(t-'request_id'-'requested_at'-'request_workflow_id')||jsonb_build_object('last_consumed_request_id',request_id);
      IF failure IS NOT NULL THEN
        failures:=1;
        IF coalesce(t->>'consecutive_failures','') ~ '^[0-9]{1,2}$' THEN
          failures:=least(20,(t->>'consecutive_failures')::integer+1);
        END IF;
        delay_seconds:=least(3600,(600*power(2,least(failures-1,3)))::integer);
        next_poll_at:=greatest(next_poll_at,checked_at+make_interval(secs=>delay_seconds));
        t:=t||jsonb_build_object('transport_status','error','last_error',failure,
          'last_error_at',checked_at,'consecutive_failures',failures);
      END IF;
      s:=jsonb_set(s,ARRAY['schedules',target],t);
    END LOOP;
    checked_at:=clock_timestamp();
    IF budget->'blocked'='false'::jsonb AND next_poll_at<=checked_at THEN
      target:=null;
      FOREACH candidate IN ARRAY ARRAY[budget->>'next_target',CASE budget->>'next_target' WHEN 'reader' THEN 'watchdog' ELSE 'reader' END] LOOP
        t:=s->'schedules'->candidate;
        target_attempt_at:=public.dufynd_scheduler_parse_time_v1(t->'last_attempt_at');
        IF t ? 'request_id' THEN CONTINUE; END IF;
        IF t ? 'last_attempt_at' AND (target_attempt_at IS NULL OR target_attempt_at>checked_at
          OR target_attempt_at>checked_at-interval '600 seconds') THEN CONTINUE; END IF;
        target:=candidate; EXIT;
      END LOOP;
      IF target IS NOT NULL THEN
        workflow_id:=CASE target WHEN 'reader' THEN 373752411 ELSE 377395476 END;
        endpoint:='https://api.github.com/repos/tncommerce/commerce-agents/actions/workflows/'||workflow_id||
          '/runs?branch=main&event=schedule&per_page=1';
        checked_at:=clock_timestamp();
        t:=s->'schedules'->target;
        t:=t||jsonb_build_object('last_attempt_at',checked_at);
        budget:=budget||jsonb_build_object('last_attempt_at',checked_at,'next_target',
          CASE target WHEN 'reader' THEN 'watchdog' ELSE 'reader' END);
        next_poll_at:=checked_at+interval '300 seconds';
        BEGIN
          EXECUTE 'select net.http_get(url:=$1,headers:=$2,timeout_milliseconds:=5000)'
            INTO request_id USING endpoint,'{"Accept":"application/vnd.github+json", "X-GitHub-Api-Version":"2026-03-10", "User-Agent":"DUFYND-Scheduler-Delivery/1"}'::jsonb;
          IF request_id IS NULL OR request_id<=0 THEN RAISE EXCEPTION 'request id unavailable'; END IF;
          t:=t||jsonb_build_object('request_id',request_id,'requested_at',checked_at,'request_workflow_id',workflow_id);
        EXCEPTION WHEN OTHERS THEN
          t:=t||jsonb_build_object('transport_status','error','last_error','request_enqueue_failed','last_error_at',checked_at);
          next_poll_at:=checked_at+interval '600 seconds';
        END;
        s:=jsonb_set(s,ARRAY['schedules',target],t);
      END IF;
    END IF;
  END IF;
  budget:=budget||jsonb_build_object('next_poll_at',next_poll_at);
  s:=jsonb_set(s,'{budget}',budget);
  UPDATE public.dufynd_master_status SET value=s,last_verified_at=clock_timestamp()
  WHERE key='ops.github_scheduler_delivery_v1';
  RETURN public.read_dufynd_github_scheduler_delivery_v1();
END
$scheduler_poll$;

REVOKE ALL ON FUNCTION public.dufynd_scheduler_parse_time_v1(jsonb) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.normalize_dufynd_github_scheduler_run_v1(text,jsonb,timestamptz) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.read_dufynd_github_scheduler_delivery_v1() FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.poll_dufynd_github_scheduler_delivery_v1() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.dufynd_scheduler_parse_time_v1(jsonb) TO postgres,service_role;
GRANT EXECUTE ON FUNCTION public.normalize_dufynd_github_scheduler_run_v1(text,jsonb,timestamptz) TO postgres,service_role;
GRANT EXECUTE ON FUNCTION public.read_dufynd_github_scheduler_delivery_v1() TO postgres,service_role;
GRANT EXECUTE ON FUNCTION public.poll_dufynd_github_scheduler_delivery_v1() TO postgres,service_role;
