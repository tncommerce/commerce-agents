-- Use only inside the migration transaction; no manual poll or external action.
set local lock_timeout='5s';
set local statement_timeout='30s';
select pg_advisory_xact_lock(hashtext('dufynd-free-planner-v1'));
select pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
do $release_guard$
declare r record;
begin
 select md5(pg_get_functiondef(p.oid)) as definition_md5,pg_get_userbyid(p.proowner) as owner,
   p.proacl::text as acl,p.prosecdef as security_definer,p.proconfig as config,p.provolatile::text as volatility
 into r from pg_proc p where p.oid=to_regprocedure('public.poll_dufynd_observers()');
 if r.definition_md5 is null or r.definition_md5 not in ('b16099ccc4633cafb48dcb81044738ad')
  or r.owner is distinct from 'postgres'
  or r.acl is distinct from '{postgres=X/postgres,service_role=X/postgres}'
  or r.security_definer is distinct from false
  or r.config is distinct from array['search_path=public']::text[]
  or r.volatility is distinct from 'v' then
   raise exception 'DUFYND release fingerprint or ACL mismatch: public.poll_dufynd_observers()';
 end if;
end;
$release_guard$;
-- Persist the same freshness truth already returned by observer health reads.
-- Private Render/Gmail observations do not become fresh from a successful cron.
-- Keep provider reads broker-only and preserve every existing permission/cursor.
-- Derived from the exact production function observed on 2026-10-28.

CREATE OR REPLACE FUNCTION public.poll_dufynd_observers()
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
declare o public.dufynd_external_observers; r record; body jsonb; url text; headers jsonb; credential_health jsonb; rid bigint; result jsonb; attempted int:=0; retry int; events jsonb;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
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
;
do $observer_postcondition$
declare r record;
begin
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
end;
$observer_postcondition$;
