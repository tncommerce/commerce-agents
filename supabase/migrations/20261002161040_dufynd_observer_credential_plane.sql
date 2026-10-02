-- NON-SECRET metadata only. Private broker Vault/lock backend is owner-selected.
create table public.dufynd_observer_credentials (
 credential_id text primary key,
 provider text not null check(provider in ('render','gmail')),
 account_alias text not null,
 allowed_operations jsonb not null,
 allowed_resources jsonb not null,
 oauth_scopes jsonb not null,
 secret_reference text not null,
 status text not null default 'missing_configuration' check(status in
 ('missing_configuration','healthy','expiring','expired','revoked','refresh_failed','scope_mismatch','account_mismatch')),
 expires_at timestamptz,refreshed_at timestamptz,revoked_at timestamptz,
 last_health_check timestamptz,rotation_due_at timestamptz,
 health_reason text not null default 'missing_configuration' check(health_reason in
 ('missing_configuration','healthy','expiring','expired','revoked','refresh_failed','scope_mismatch','account_mismatch',
  'rate_limited','provider_outage','rotation_secret_missing','refresh_race','invalid_grant','invalid_response','broker_activation_required')),
 activation_enabled boolean not null default false,
 check (
  (provider='render' and credential_id='render_deploy_broker' and account_alias='tncommerce_render'
   and allowed_operations='["deployment.read"]'::jsonb and allowed_resources='["srv-dakpfrnf3r2c73dr3f20"]'::jsonb
   and oauth_scopes='[]'::jsonb and secret_reference='dufynd_observer_render_read_token')
  or
  (provider='gmail' and credential_id='gmail_known_threads' and account_alias='dufynd_owner_mailbox'
   and allowed_operations='["thread.metadata","history.read"]'::jsonb
   and allowed_resources='["1a0f385ed98c6af8","1a0f69c169fb928f","1a0f6a90772a743d"]'::jsonb
   and oauth_scopes='["https://www.googleapis.com/auth/gmail.metadata"]'::jsonb
   and secret_reference='dufynd_observer_gmail_read_access_token')
 )
);
alter table public.dufynd_observer_credentials enable row level security;
revoke all on public.dufynd_observer_credentials from public,anon,authenticated;
grant select,insert,update,delete on public.dufynd_observer_credentials to service_role;
insert into public.dufynd_observer_credentials(credential_id,provider,account_alias,allowed_operations,allowed_resources,oauth_scopes,secret_reference)
values ('render_deploy_broker','render','tncommerce_render','["deployment.read"]','["srv-dakpfrnf3r2c73dr3f20"]','[]','dufynd_observer_render_read_token'),
 ('gmail_known_threads','gmail','dufynd_owner_mailbox','["thread.metadata","history.read"]','["1a0f385ed98c6af8","1a0f69c169fb928f","1a0f6a90772a743d"]','["https://www.googleapis.com/auth/gmail.metadata"]','dufynd_observer_gmail_read_access_token');

create function public.get_dufynd_credential_health(p_provider text) returns jsonb
language sql stable security invoker set search_path=public as $$
select coalesce((select jsonb_build_object('credential_id',credential_id,'provider',provider,
 'status',case when revoked_at is not null then 'revoked'
  when status in ('missing_configuration','expired','revoked','refresh_failed','scope_mismatch','account_mismatch') then status
  when expires_at<=now() then 'expired'
  when provider='gmail' and expires_at is null then 'missing_configuration'
  when expires_at<=now()+interval '5 minutes' then 'expiring' else status end,
 'health_reason',health_reason,'expires_at',expires_at,'refreshed_at',refreshed_at,
 'revoked_at',revoked_at,'last_health_check',last_health_check,'rotation_due_at',rotation_due_at,
 'activation_enabled',activation_enabled,
 'owner_reauthorization_required',revoked_at is not null or status in ('revoked','account_mismatch') or health_reason='invalid_grant',
 'waiting_human_input',false)
 from public.dufynd_observer_credentials where provider=p_provider),
 jsonb_build_object('provider',p_provider,'status','missing_configuration','activation_enabled',false,'waiting_human_input',false));
$$;

-- Integration reuses the existing normalizer/inbox/dedupe/waits. The private
-- broker sends only filtered evidence, never its upstream auth response/token.
create function public.capture_dufynd_broker_observation(p_credential_id text,p_observer_id text,p_evidence jsonb)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare c public.dufynd_observer_credentials; o public.dufynd_external_observers;
 health jsonb; raw jsonb; x jsonb; messages jsonb:='[]'; deployments jsonb:='[]';
begin
 select * into c from public.dufynd_observer_credentials where credential_id=p_credential_id;
 select * into o from public.dufynd_external_observers where observer_id=p_observer_id;
 health:=public.get_dufynd_credential_health(c.provider);
 if c.credential_id is null or o.observer_id is null or c.provider is distinct from o.source_type
 or not c.allowed_resources ? o.source_id or not c.activation_enabled
 or health->>'status' not in ('healthy','expiring') or c.last_health_check is null or c.last_health_check<now()-interval '5 minutes' or not o.enabled then
  return jsonb_build_object('accepted',false,'reason','blocked_configuration');
 end if;
 if p_evidence is null or octet_length(p_evidence::text)>65536 then raise exception 'invalid bounded broker evidence'; end if;
 if c.provider='render' then
  if jsonb_typeof(p_evidence) is distinct from 'array' or jsonb_array_length(p_evidence)>20 then raise exception 'invalid deployment evidence'; end if;
  for x in select value from jsonb_array_elements(p_evidence) loop
   if jsonb_typeof(x) is distinct from 'object' or x-array['deployment_id','service_id','commit_sha','status','timestamps']<>'{}'::jsonb
   or x->>'service_id' is distinct from o.source_id or coalesce(x->>'deployment_id','') !~ '^dep-[a-z0-9]+$'
   or coalesce(x->>'commit_sha','') !~ '^[a-f0-9]{40}$'
   or coalesce(x->>'status','') not in ('live','created','queued','build_in_progress','update_in_progress','pre_deploy_in_progress','build_failed','update_failed','pre_deploy_failed','canceled','deactivated')
   then raise exception 'broker resource/shape mismatch'; end if;
   -- Timestamps are allowed upstream output; only identity/state enter events.
   deployments:=deployments||jsonb_build_array(jsonb_build_object('id',x->>'deployment_id','status',x->>'status','commit',jsonb_build_object('id',x->>'commit_sha')));
  end loop;
  raw:=deployments;
 else
  if jsonb_typeof(p_evidence) is distinct from 'object'
  or p_evidence-array['thread_id','history_id','messages']<>'{}'::jsonb
  or p_evidence->>'thread_id' is distinct from o.source_id or coalesce(p_evidence->>'history_id','') !~ '^[0-9]{1,30}$'
  or jsonb_typeof(p_evidence->'messages') is distinct from 'array' or jsonb_array_length(p_evidence->'messages')>100 then raise exception 'invalid thread evidence'; end if;
  for x in select value from jsonb_array_elements(p_evidence->'messages') loop
   if jsonb_typeof(x) is distinct from 'object' or x-array['message_id','thread_id','internal_date','sender','delivery_failure']<>'{}'::jsonb
   or x->>'thread_id' is distinct from o.source_id or coalesce(x->>'message_id','') !~ '^[a-f0-9]{1,32}$'
   or coalesce(x->>'internal_date','') !~ '^[0-9]{1,16}$' or jsonb_typeof(x->'delivery_failure') is distinct from 'boolean'
   or length(coalesce(x->>'sender',''))>320 or (coalesce(x->>'sender','')<>'' and x->>'sender' !~ '^[a-z0-9.!#$%&''*+/=?^_`{|}~-]+@[a-z0-9.-]+$') then raise exception 'foreign/invalid message rejected'; end if;
   messages:=messages||jsonb_build_array(jsonb_build_object('id',x->>'message_id','threadId',o.source_id,'internalDate',x->>'internal_date',
    'payload',jsonb_build_object('headers',jsonb_build_array(
     jsonb_build_object('name','From','value',x->>'sender'),
     jsonb_build_object('name','Content-Type','value',case when (x->>'delivery_failure')::boolean then 'delivery-status' else '' end)))));
  end loop;
  raw:=jsonb_build_object('id',o.source_id,'historyId',p_evidence->>'history_id','messages',messages);
 end if;
 return public.capture_dufynd_observation(p_observer_id,raw);
end $$;

revoke all on function public.get_dufynd_credential_health(text),public.capture_dufynd_broker_observation(text,text,jsonb) from public,anon,authenticated;
grant execute on function public.get_dufynd_credential_health(text),public.capture_dufynd_broker_observation(text,text,jsonb) to service_role;

-- Preserve the GitHub observer; Render/Gmail push only through the private broker.
create or replace function public.poll_dufynd_observers() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare o public.dufynd_external_observers; r record; body jsonb; url text; headers jsonb; credential_health jsonb; rid bigint; result jsonb; attempted int:=0; retry int; events jsonb;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 update public.dufynd_external_observers set health_status='stale',last_error='observer_success_stale'
 where enabled and source_type in ('github_branch','github_pr','github_ci','github_workflow') and health_status in ('healthy','degraded') and coalesce(last_success_at,last_attempt_at,'-infinity')<now()-make_interval(secs=>greatest(600,interval_seconds*3));
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
end $$;


alter function public.get_dufynd_observer_health() rename to get_dufynd_observer_health_base;
create function public.get_dufynd_observer_health() returns jsonb
language sql stable security invoker set search_path=public as $$
select coalesce(jsonb_agg(x||case when x->>'source_type' in ('render','gmail') then
 jsonb_build_object('credential_health',public.get_dufynd_credential_health(x->>'source_type')) else '{}'::jsonb end),'[]')
from jsonb_array_elements(public.get_dufynd_observer_health_base()) x;
$$;

alter function public.normalize_dufynd_observation(text,text,jsonb,jsonb) rename to normalize_dufynd_observation_base;
create function public.normalize_dufynd_observation(p_type text,p_id text,p_raw jsonb,p_config jsonb default '{}')
returns jsonb language plpgsql security invoker set search_path=public as $$
declare events jsonb; x jsonb; sender text; output jsonb:='[]';
begin
 events:=public.normalize_dufynd_observation_base(p_type,p_id,p_raw,p_config);
 if p_type<>'gmail' or not p_raw ? 'messages' then return events; end if;
 for x in select value from jsonb_array_elements(events) loop
  select lower(h->>'value') into sender
  from jsonb_array_elements(p_raw->'messages') m,
   jsonb_array_elements(coalesce(m->'payload'->'headers','[]')) h
  where m->>'id'=x->'payload'->>'message_id' and lower(h->>'name')='from'
   and length(h->>'value')<=320 and lower(h->>'value') ~ '^[a-z0-9.!#$%&''*+/=?^_`{|}~-]+@[a-z0-9.-]+$' limit 1;
  output:=output||jsonb_build_array(jsonb_set(x,'{payload}',(x->'payload')||jsonb_build_object('sender',coalesce(sender,''))));
 end loop;
 return output;
end $$;
revoke all on function public.get_dufynd_observer_health_base(),public.get_dufynd_observer_health(),
 public.normalize_dufynd_observation_base(text,text,jsonb,jsonb),public.normalize_dufynd_observation(text,text,jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.get_dufynd_observer_health_base(),public.get_dufynd_observer_health(),
 public.normalize_dufynd_observation_base(text,text,jsonb,jsonb),public.normalize_dufynd_observation(text,text,jsonb,jsonb) to service_role;
