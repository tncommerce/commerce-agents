-- Public API liveness is independent from the private Render/Gmail broker chain.
-- No cron, credential, provider activation, private capture or task is created.
-- pg_net follows redirects: only our fixed, trusted public endpoint is requested;
-- this is not a pinned-origin, deployed-revision or private-provider proof.

INSERT INTO public.dufynd_master_status(key,category,value,priority,last_verified_at)
VALUES ('ops.public_api_health_v1','operations',jsonb_build_object(
  'version',1,'enabled',false,'status','disabled','config_checked_at',now(),
  'endpoint','https://scentai-api-kxhe.onrender.com/api/health',
  'scope','public_api_liveness_only','interval_seconds',120,'freshness_seconds',600,
  'private_observer_evidence',false,'full_chain_complete',false
),90,now())
ON CONFLICT(key) DO NOTHING;

CREATE OR REPLACE FUNCTION public.read_dufynd_public_api_health_v1()
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER
SET search_path TO pg_catalog,public
AS $monitor_read$
DECLARE
 s jsonb; result jsonb; success_at timestamptz; valid_until timestamptz;
 requested_at timestamptz; observed_at timestamptz:=clock_timestamp();
 status text;
BEGIN
 SELECT value INTO s FROM public.dufynd_master_status WHERE key='ops.public_api_health_v1';
 IF jsonb_typeof(s) IS DISTINCT FROM 'object' THEN s:='{}'::jsonb; END IF;
 result:=jsonb_build_object(
   'version',1,'enabled',s->'enabled'='true'::jsonb,
   'endpoint','https://scentai-api-kxhe.onrender.com/api/health',
   'scope','public_api_liveness_only','private_observer_evidence',false,
   'full_chain_complete',false,'healthy',false,'observed_at',observed_at,
   'interval_seconds',120,'freshness_seconds',600,
   'last_success_at',s->'last_success_at','valid_until',s->'valid_until',
   'last_attempt_at',s->'last_attempt_at','next_poll_at',s->'next_poll_at',
   'last_error',s->'last_error','last_status_code',s->'last_status_code',
   'consecutive_failures',s->'consecutive_failures','request_pending',s ? 'request_id'
 );
 IF s->'enabled' IS DISTINCT FROM 'true'::jsonb THEN
   RETURN result||jsonb_build_object('status','disabled','enabled',false);
 END IF;
 BEGIN success_at:=(s->>'last_success_at')::timestamptz;
 EXCEPTION WHEN OTHERS THEN success_at:=null; END;
 BEGIN valid_until:=(s->>'valid_until')::timestamptz;
 EXCEPTION WHEN OTHERS THEN valid_until:=null; END;
 BEGIN requested_at:=(s->>'requested_at')::timestamptz;
 EXCEPTION WHEN OTHERS THEN requested_at:=null; END;
 status:=coalesce(s->>'status','unavailable');
 IF status='healthy' THEN
   IF success_at IS NULL OR valid_until IS NULL OR NOT isfinite(success_at)
      OR NOT isfinite(valid_until) OR success_at>observed_at
      OR success_at<observed_at-interval '600 seconds'
      OR valid_until<>success_at+interval '600 seconds' OR valid_until<observed_at
      OR s->'last_status_code' IS DISTINCT FROM '200'::jsonb THEN
     RETURN result||jsonb_build_object('status','stale','last_error','api_success_stale');
   END IF;
   RETURN result||jsonb_build_object('status','healthy','healthy',true);
 END IF;
 IF status='pending' AND (requested_at IS NULL OR NOT isfinite(requested_at)
    OR requested_at>observed_at OR requested_at<observed_at-interval '60 seconds') THEN
   RETURN result||jsonb_build_object('status','unavailable','last_error','request_overdue');
 END IF;
 IF status NOT IN ('pending','unhealthy','unavailable','stale') THEN status:='unavailable'; END IF;
 RETURN result||jsonb_build_object('status',status);
END
$monitor_read$;

CREATE OR REPLACE FUNCTION public.poll_dufynd_public_api_health_v1()
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER
SET search_path TO pg_catalog,public
AS $monitor_poll$
DECLARE
 s jsonb; response record; body jsonb; request_id bigint;
 observed_at timestamptz:=clock_timestamp(); requested_at timestamptz;
 next_poll_at timestamptz; failure text; failures integer:=0; delay_seconds integer;
 response_count integer; queued boolean;
BEGIN
 IF NOT pg_try_advisory_xact_lock(hashtext('dufynd-public-api-health-v1')) THEN
   RETURN public.read_dufynd_public_api_health_v1()||jsonb_build_object('poll_busy',true);
 END IF;
 SELECT value INTO s FROM public.dufynd_master_status
 WHERE key='ops.public_api_health_v1' FOR UPDATE;
 observed_at:=clock_timestamp();
 IF jsonb_typeof(s) IS DISTINCT FROM 'object' OR s->'enabled' IS DISTINCT FROM 'true'::jsonb THEN
   RETURN public.read_dufynd_public_api_health_v1();
 END IF;
 -- Configuration is fixed in code; the status row cannot supply URLs or headers.
 s:=s||jsonb_build_object('version',1,'endpoint','https://scentai-api-kxhe.onrender.com/api/health',
   'scope','public_api_liveness_only','private_observer_evidence',false,
   'full_chain_complete',false,'interval_seconds',120,'freshness_seconds',600);
 IF coalesce(s->>'consecutive_failures','') ~ '^[0-9]{1,2}$' THEN
   failures:=least(20,(s->>'consecutive_failures')::integer);
 END IF;
 BEGIN next_poll_at:=(s->>'next_poll_at')::timestamptz;
 EXCEPTION WHEN OTHERS THEN next_poll_at:=null; END;
 IF next_poll_at IS NOT NULL AND (NOT isfinite(next_poll_at)
    OR next_poll_at>observed_at+interval '30 minutes') THEN next_poll_at:=null; END IF;

 IF to_regnamespace('net') IS NULL OR to_regclass('net._http_response') IS NULL THEN
   failure:='pg_net_unavailable';
 ELSIF s ? 'request_id' THEN
   BEGIN requested_at:=(s->>'requested_at')::timestamptz;
   EXCEPTION WHEN OTHERS THEN requested_at:=null; END;
   IF coalesce(s->>'request_id','') !~ '^[1-9][0-9]{0,17}$'
      OR requested_at IS NULL OR NOT isfinite(requested_at) OR requested_at>observed_at THEN
     failure:='invalid_pending_state';
   ELSE
     request_id:=(s->>'request_id')::bigint;
     EXECUTE 'select status_code,content_type,content,timed_out,error_msg,created from net._http_response where id=$1'
       INTO response USING request_id;
     GET DIAGNOSTICS response_count=ROW_COUNT;
     observed_at:=clock_timestamp();
     IF response_count=0 THEN
       IF requested_at>observed_at-interval '60 seconds' THEN
         RETURN public.read_dufynd_public_api_health_v1();
       END IF;
       -- An unavailable pg_net worker may still own our queued request. Keep
       -- that identity so repeated cron ticks cannot build a request backlog.
       IF to_regclass('net.http_request_queue') IS NOT NULL THEN
         EXECUTE 'select exists(select 1 from net.http_request_queue where id=$1)'
           INTO queued USING request_id;
         IF queued THEN
           s:=s||jsonb_build_object('status','unavailable',
             'last_error','request_dispatch_overdue','last_error_at',observed_at);
           UPDATE public.dufynd_master_status SET value=s,last_verified_at=observed_at
           WHERE key='ops.public_api_health_v1';
           RETURN public.read_dufynd_public_api_health_v1();
         END IF;
       END IF;
       failure:='response_missing';
     ELSIF coalesce(response.timed_out,false) OR response.error_msg IS NOT NULL THEN
       failure:='transport_failure';
     ELSIF response.status_code IS DISTINCT FROM 200 THEN
       failure:='http_status_rejected';
     ELSIF response.created IS NULL OR NOT isfinite(response.created)
        OR response.created<requested_at OR response.created>observed_at
        OR response.created<observed_at-interval '600 seconds' THEN
       failure:='response_not_fresh';
     ELSIF btrim(split_part(lower(coalesce(response.content_type,'')),';',1))<>'application/json' THEN
       failure:='content_type_rejected';
     ELSIF response.content IS NULL OR octet_length(response.content)>16384 THEN
       failure:='response_size_rejected';
     ELSE
       BEGIN body:=response.content::jsonb;
       EXCEPTION WHEN OTHERS THEN body:=null; END;
       IF jsonb_typeof(body) IS DISTINCT FROM 'object'
          OR body->'ok' IS DISTINCT FROM 'true'::jsonb
          OR body->>'store' IS DISTINCT FROM 'DUFYND' THEN
         failure:='health_payload_rejected';
       ELSE
         s:=s||jsonb_build_object('status','healthy','last_success_at',response.created,
           'valid_until',response.created+interval '600 seconds','response_checked_at',observed_at,
           'last_status_code',200,'last_error',null,'consecutive_failures',0,
           'next_poll_at',response.created+interval '120 seconds');
         failures:=0; next_poll_at:=response.created+interval '120 seconds';
       END IF;
     END IF;
     -- Retain only an HTTP code, never provider response/error text.
     IF response_count>0 THEN s:=s||jsonb_build_object('last_status_code',response.status_code); END IF;
   END IF;
   s:=s-'request_id'-'requested_at';
 END IF;

 IF failure IS NOT NULL THEN
   failures:=least(20,failures+1);
   delay_seconds:=least(1800,(120*power(2,least(failures-1,4)))::integer);
   s:=(s-'request_id'-'requested_at')||jsonb_build_object(
     'status',CASE WHEN failure IN ('http_status_rejected','health_payload_rejected')
       THEN 'unhealthy' ELSE 'unavailable' END,
     'last_error',failure,'last_error_at',observed_at,'consecutive_failures',failures,
     'next_poll_at',observed_at+make_interval(secs=>delay_seconds));
 ELSIF NOT s ? 'request_id' AND coalesce(next_poll_at,'-infinity'::timestamptz)<=observed_at THEN
   BEGIN
     EXECUTE 'select net.http_get(url:=$1,headers:=$2,timeout_milliseconds:=5000)'
       INTO request_id USING 'https://scentai-api-kxhe.onrender.com/api/health',
       '{"Accept":"application/json","User-Agent":"DUFYND-Public-API-Health/1"}'::jsonb;
     IF request_id IS NULL OR request_id<=0 THEN RAISE EXCEPTION 'request id unavailable'; END IF;
     s:=s||jsonb_build_object('request_id',request_id,'requested_at',observed_at,
       'last_attempt_at',observed_at,'next_poll_at',observed_at+interval '120 seconds');
     IF s->>'status' IS DISTINCT FROM 'healthy' THEN s:=s||'{"status":"pending"}'::jsonb; END IF;
   EXCEPTION WHEN OTHERS THEN
     failures:=least(20,failures+1);
     delay_seconds:=least(1800,(120*power(2,least(failures-1,4)))::integer);
     s:=(s-'request_id'-'requested_at')||jsonb_build_object('status','unavailable',
       'last_error','request_enqueue_failed','last_error_at',observed_at,
       'consecutive_failures',failures,'next_poll_at',observed_at+make_interval(secs=>delay_seconds));
   END;
 END IF;
 UPDATE public.dufynd_master_status SET value=s,last_verified_at=observed_at
 WHERE key='ops.public_api_health_v1';
 RETURN public.read_dufynd_public_api_health_v1();
EXCEPTION WHEN OTHERS THEN
 BEGIN
   UPDATE public.dufynd_master_status SET value=value||jsonb_build_object(
     'status','unavailable','last_error','monitor_internal_error','last_error_at',clock_timestamp()),
     last_verified_at=clock_timestamp() WHERE key='ops.public_api_health_v1';
 EXCEPTION WHEN OTHERS THEN
   RAISE LOG 'DUFYND public API health status persistence unavailable';
 END;
 RETURN jsonb_build_object('status','unavailable','healthy',false,
   'last_error','monitor_internal_error','scope','public_api_liveness_only',
   'private_observer_evidence',false,'full_chain_complete',false);
END
$monitor_poll$;

REVOKE ALL ON FUNCTION public.read_dufynd_public_api_health_v1() FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.poll_dufynd_public_api_health_v1() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.read_dufynd_public_api_health_v1() TO service_role;
GRANT EXECUTE ON FUNCTION public.poll_dufynd_public_api_health_v1() TO service_role;

-- Existing production poll body follows; the isolated monitor is the only hook.

CREATE OR REPLACE FUNCTION public.poll_dufynd_observers()
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
declare o public.dufynd_external_observers; r record; body jsonb; url text; headers jsonb; credential_health jsonb; rid bigint; result jsonb; attempted int:=0; retry int; events jsonb;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 begin
  perform public.poll_dufynd_public_api_health_v1();
 exception when others then
  raise log 'DUFYND public API health hook unavailable';
 end;
 update public.dufynd_external_observers set health_status='stale',last_error='observer_success_stale'
 where enabled and source_type in ('github_branch','github_pr','github_ci','github_workflow','render','gmail') and health_status in ('healthy','degraded') and coalesce(last_success_at,last_attempt_at,'-infinity')<now()-make_interval(secs=>greatest(600,interval_seconds*3));
 if to_regnamespace('net') is null then return jsonb_build_object('available',false); end if;
 for o in select * from public.dufynd_external_observers where request_id is not null and source_type not in ('render','gmail') for update loop
  execute 'select status_code,content,headers,timed_out,error_msg from net._http_response where id=$1' into r using o.request_id;
  if r.status_code is null and o.request_started_at>now()-interval '60 seconds' then continue; end if;
  if r.status_code=304 then
   update public.dufynd_external_observers set last_success_at=now(),health_status='healthy',consecutive_failures=0,last_error=null,request_id=null,request_started_at=null,next_retry_at=now()+make_interval(secs=>interval_seconds) where observer_id=o.observer_id;
   continue;
  end if;
  if r.status_code is distinct from 200 then
   retry:=case when coalesce(r.headers->>'retry-after','') ~ '^[0-9]{1,5}$' then least(3600,(r.headers->>'retry-after')::int) else null end;
   perform public.dufynd_observer_failure(o.observer_id,case when r.status_code=404 and o.source_type='gmail' then 'gmail_history_expired'
    when r.status_code=429 or (r.status_code=403 and r.headers->>'x-ratelimit-remaining'='0') then 'rate_limited' else 'external_transport_failure' end,coalesce(r.status_code,0),retry);
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
   if o.source_type='gmail' and o.request_kind='thread' and o.pending_cursor is not null then
    update public.dufynd_external_observers set last_cursor=case when o.pending_page_token is not null then o.last_cursor else o.pending_cursor end,
      page_token=o.pending_page_token,pending_cursor=null,pending_page_token=null,request_kind=null where observer_id=o.observer_id;
   end if;
   update public.dufynd_external_observers set etag=coalesce(r.headers->>'etag',r.headers->>'ETag',etag) where observer_id=o.observer_id;
  exception when others then perform public.dufynd_observer_failure(o.observer_id,'invalid_bounded_source_response'); end;
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
  and request_id is null and next_retry_at<=now() order by next_retry_at,last_attempt_at nulls first limit 1 for update;
 if not found then return jsonb_build_object('attempted',0); end if;
 headers:='{"Accept":"application/json","User-Agent":"DUFYND-Supervisor-V2","X-GitHub-Api-Version":"2022-11-28"}';
 if o.etag is not null then headers:=headers||jsonb_build_object('If-None-Match',o.etag); end if;
 if o.source_type='github_branch' then url:='https://api.github.com/repos/tncommerce/commerce-agents/branches/scentai-mvp';
 elsif o.source_type='github_pr' then url:='https://api.github.com/repos/tncommerce/commerce-agents/pulls/'||o.source_id;
 elsif o.source_type in ('github_ci','github_workflow') then url:='https://api.github.com/repos/tncommerce/commerce-agents/actions/runs/'||o.source_id;
 else return jsonb_build_object('attempted',0); end if;
 execute 'select net.http_get(url:=$1,headers:=$2,timeout_milliseconds:=5000)' into rid using url,headers;
 update public.dufynd_external_observers set request_id=rid,request_started_at=now(),last_attempt_at=now() where observer_id=o.observer_id;
 return jsonb_build_object('attempted',1);
end $function$
