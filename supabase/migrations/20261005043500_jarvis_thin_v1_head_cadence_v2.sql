-- Align Thin V1 live-head freshness with the real observer round-robin cadence.
-- The observer reconciler polls one observer per pass. A healthy scentai-mvp observation
-- can therefore be several minutes old even while the observer subsystem is operating.
-- Keep fail-closed identity/CI checks, but use the observer subsystem's 10-minute stale bound.
create or replace function public.poll_dufynd_thin_ci() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare o public.dufynd_external_observers; s jsonb; r record; b jsonb; run jsonb; rid bigint;
begin
 select * into o from public.dufynd_external_observers where observer_id='github_branch:scentai-mvp';
 select value into s from public.dufynd_master_status where key='jarvis.thin_v1.ci';
 if o.enabled is distinct from true or o.health_status is distinct from 'healthy'
 or coalesce(o.last_success_at,'-infinity')<now()-interval '10 minutes'
 or coalesce(o.last_snapshot->>'sha','') !~ '^[a-f0-9]{40}$'
 then return jsonb_build_object('ready',false,'reason','stale_live_head'); end if;
 if s->>'sha' is distinct from o.last_snapshot->>'sha' then s:=jsonb_build_object('sha',o.last_snapshot->>'sha','ready',false); end if;
 if s->>'request_id' is not null then
  select status_code,content,timed_out,error_msg into r from net._http_response where id=(s->>'request_id')::bigint;
  if r.status_code is null and public.dufynd_parse_timestamp(s->>'requested_at')>now()-interval '60 seconds' then return s; end if;
  s:=s-'request_id';
  if r.status_code=200 and length(r.content)<1000000 then
   begin
    b:=r.content::jsonb; run:=b->'workflow_runs'->0;
    if run->>'head_sha'=o.last_snapshot->>'sha' and run->>'head_branch'='scentai-mvp'
    and run->>'path'='.github/workflows/ci.yml' and run->>'event'='push'
    and run->'repository'->>'full_name'='tncommerce/commerce-agents' then
     s:=s||jsonb_build_object('ready',run->>'status'='completed' and run->>'conclusion'='success',
      'run_id',run->>'id','status',run->>'status','conclusion',run->>'conclusion','checked_at',now(),'reason','ci_observed');
    else s:=s||jsonb_build_object('ready',false,'reason','ci_identity_or_run_missing'); end if;
   exception when others then s:=s||jsonb_build_object('ready',false,'reason','invalid_ci_response'); end;
  else s:=s||jsonb_build_object('ready',false,'reason','ci_transport_unavailable'); end if;
  s:=s||jsonb_build_object('next_poll_at',now()+interval '10 minutes');
 end if;
 if coalesce(public.dufynd_parse_timestamp(s->>'next_poll_at'),'-infinity')<=now() then
  rid:=net.http_get(url:='https://api.github.com/repos/tncommerce/commerce-agents/actions/workflows/ci.yml/runs',
   params:=jsonb_build_object('branch','scentai-mvp','head_sha',o.last_snapshot->>'sha','event','push','per_page','1'),
   headers:='{"Accept":"application/vnd.github+json","User-Agent":"DUFYND-Free-Supervisor"}',timeout_milliseconds:=5000);
  s:=s||jsonb_build_object('request_id',rid,'requested_at',now());
 end if;
 if coalesce(public.dufynd_parse_timestamp(s->>'checked_at'),'-infinity')<now()-interval '20 minutes' then
  s:=s||jsonb_build_object('ready',false,'reason','ci_evidence_stale');
 end if;
 insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
 values('jarvis.thin_v1.ci','jarvis',s,100,now())
 on conflict(key) do update set value=excluded.value,last_verified_at=excluded.last_verified_at;
 return s;
end $$;

revoke all on function public.poll_dufynd_thin_ci() from public,anon,authenticated;
grant execute on function public.poll_dufynd_thin_ci() to service_role;
