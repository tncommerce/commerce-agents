-- pg_net retains responses independently of the supervisor consumer. Receipt
-- time, not the later poll transaction, is the source of observation freshness.
-- Replace only the existing poller; keep its ACL, cadence and private hook.
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

-- The previous 200 path kept an old ETag when a new body omitted its validator.
-- Clear that unproven pairing once; preserve snapshots, source times, pending
-- identities, retry deadlines and disabled/private observer configuration.
-- The next already-due GET rebaselines; legacy in-flight 304 fails closed.
UPDATE public.dufynd_external_observers SET etag=null
 WHERE source_type in ('github_branch','github_pr','github_ci','github_workflow')
   AND etag IS NOT NULL;
