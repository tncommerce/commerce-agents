-- Thin V1 uses the existing queue, packets, verifier and supervisor fences.
-- Disabled until the scentai-mvp PR and live runtime acceptance are verified.
insert into public.dufynd_master_status(key,category,value,priority)
values('jarvis.thin_v1.config','jarvis','{"enabled":false,"revision":1}',100)
on conflict(key) do nothing;

create function public.dufynd_thin_gate(t jsonb) returns text
language sql immutable security invoker set search_path=public as $$
select case
 when t->>'requires_human_approval'='true' then coalesce(nullif(t->>'approval_action_type',''),'owner_decision')
 when coalesce(t->>'approval_action_type','auto_allowed') not in ('auto_allowed','') then t->>'approval_action_type'
 when t->>'budget_class' is distinct from 'free' then 'paid_model_call'
 when t->>'provider_cost_unknown' is distinct from 'false' then 'provider_cost_unknown'
 when exists(select 1 from jsonb_array_elements_text(case when jsonb_typeof(t->'required_capabilities')='array' then t->'required_capabilities' else '[]' end) c
  where c in ('social.publish','budget.spend','main.merge','commerce.activate','gmail.send','external.outreach','credentials','destructive','irreversible','model.call','paid_model_call')) then 'forbidden_capability'
 else null end;
$$;

-- Public repository GET only. No credentials, models, dispatch or webhook.
-- The existing branch observer supplies a fresh HEAD. Stale/failed CI blocks work.
create function public.poll_dufynd_thin_ci() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare o public.dufynd_external_observers; s jsonb; r record; b jsonb; run jsonb; rid bigint;
begin
 select * into o from public.dufynd_external_observers where observer_id='github_branch:scentai-mvp';
 select value into s from public.dufynd_master_status where key='jarvis.thin_v1.ci';
 if o.enabled is distinct from true or o.health_status is distinct from 'healthy' or coalesce(o.last_success_at,'-infinity')<now()-interval '10 minutes'
 or coalesce(o.last_snapshot->>'sha','') !~ '^[a-f0-9]{40}$' then return jsonb_build_object('ready',false,'reason','stale_live_head'); end if;
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

create function public.read_dufynd_thin_state() returns jsonb
language sql security invoker set search_path=public as $$
select jsonb_build_object('version',1,'observed_at',now(),
 'queue_counts',(select coalesce(jsonb_object_agg(status,n),'{}') from (select status,count(*) n from public.dufynd_autonomy_tasks group by status) q),
 'active_leases',(select count(*) from public.dufynd_autonomy_tasks where released_at is null and worker_state in ('claimed','working','verifying')),
 'stale_leases',(select count(*) from public.dufynd_autonomy_tasks where released_at is null and worker_state in ('claimed','working','verifying') and coalesce(lease_expires_at,'-infinity')<=now()),
 'open_reservations',(select count(*) from public.dufynd_budget_reservations where status in ('reserved','dispatched','cost_unknown')),
 'provider_cost_unknown',exists(select 1 from public.dufynd_autonomy_tasks where provider_cost_unknown),
 'pending_owner_gates',(select coalesce(jsonb_agg(jsonb_build_object('decision_id',decision_id,'decision_token',decision_token,'action_type',action_type) order by created_at),'[]') from public.dufynd_human_decisions where status='pending'),
 'ci',(select value from public.dufynd_master_status where key='jarvis.thin_v1.ci'),
 'supervisor_checked_at',(select last_verified_at from public.dufynd_master_status where key='jarvis.supervisor_v2.health'),
 'business_checkpoint',(select jsonb_build_object('verified_at',last_verified_at,'age_seconds',extract(epoch from now()-last_verified_at),'measurement',value->'measurement','first_money_schedule',value->'first_money_schedule','schedule_source','ceo_checkpoint_only','publication_verified',false) from public.dufynd_master_status where key='continuity.checkpoint.ceo_radar'),
 'recent_first_money_events',(select coalesce(jsonb_agg(jsonb_build_object('event_id',event_id,'event_type',event_type,'observed_at',observed_at)),'[]') from (select event_id,event_type,observed_at from public.dufynd_jarvis_inbox where observed_at>now()-interval '24 hours' and (payload::text like '%one_million%' or payload::text like '%FIRST-MONEY%' or payload::text like '%fms_1m%') order by observed_at desc limit 20) e),
 'observer_health',public.get_dufynd_observer_health(),
 'paid_calls_this_loop',0,'new_spend_usd',0,'budget_window_used',null,
 'limitations','No publishing, activation, outreach, credentials, arbitrary engineering or paid workers. Social schedule is a checkpoint assertion; sales/commission need network evidence.');
$$;

-- The certified audit now includes revenue/schedule freshness without changing its tools.
alter function public.read_dufynd_supervisor_audit() rename to read_dufynd_supervisor_audit_pre_thin;
create function public.read_dufynd_supervisor_audit() returns jsonb
language sql security invoker set search_path=public as $$
select public.read_dufynd_supervisor_audit_pre_thin()||jsonb_build_object('thin_v1',public.read_dufynd_thin_state());
$$;

create function public.run_dufynd_thin_v1() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare ci jsonb; t public.dufynd_autonomy_tasks; e public.dufynd_execution_runs; p jsonb;
 result jsonb:='[]'; reason text:='no_safe_work'; gate text; token text; did text; report jsonb; tid text; i int;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 if not coalesce((select value->>'enabled'='true' from public.dufynd_master_status where key='jarvis.thin_v1.config'),false) then
  return jsonb_build_object('stop_reason','disabled','paid_calls',0); end if;
 ci:=public.poll_dufynd_thin_ci();
 if ci->>'ready' is distinct from 'true' then reason:='waiting_external';
 else
  -- One meaningful metadata audit per 30-minute slot, never synthetic busywork.
  tid:='thin-health:'||to_char(now() at time zone 'UTC','YYYYMMDDHH24')||case when extract(minute from now())<30 then '00' else '30' end;
  insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,priority,budget_class,resource_scope,durability_policy,durable_payload)
  values(tid,'supervisor','Free First-Money and supervisor health audit','Persist metadata evidence only.','ready',100,'free','["db:jarvis.supervisor_v2.health"]','durable','{"kind":"supervisor_state_audit","steps":1,"interval_seconds":2}') on conflict(task_id) do nothing;
  for i in 1..4 loop
   t:=null;
   -- Internal/external dependencies and resource collisions are checked before gate/claim.
   select q.* into t from public.dufynd_autonomy_tasks q where q.status in ('ready','approval_required','waiting_human_input')
    and jsonb_typeof(q.dependencies)='array'
    and not exists(select 1 from jsonb_array_elements_text(q.dependencies) d where not exists(select 1 from public.dufynd_autonomy_tasks x where x.task_id=d and x.status='done'))
    and not exists(select 1 from public.dufynd_task_external_waits w where w.task_id=q.task_id and (not w.satisfied or w.policy<>'dependency'))
    and not coalesce(q.released_at is null and q.lease_expires_at>now(),false)
    and not exists(select 1 from public.dufynd_autonomy_tasks x where x.task_id<>q.task_id and x.released_at is null and x.lease_expires_at>now() and x.worker_state in ('claimed','working','verifying') and public.dufynd_resources_conflict(q.resource_scope,x.resource_scope))
    and (public.dufynd_thin_gate(to_jsonb(q)) is not null or
     (q.status='ready' and not q.external_review_required and not q.needs_freshness_recheck and q.durable_payload is not null
      and q.durable_payload->>'kind' in ('supervisor_state_audit','purchase_destination_freshness_audit','ci_pr_verifier')
      and public.select_dufynd_handler(q.task_id,'supervisor',q.resource_scope,q.durable_payload,q.durability_policy) is not null))
    order by q.priority desc,q.created_at,q.task_id limit 1 for update;
   if t.task_id is null then exit; end if;
   gate:=public.dufynd_thin_gate(to_jsonb(t));
   if gate is not null then
    did:='thin-gate:'||t.task_id||':'||substr(encode(sha256(convert_to(jsonb_build_array(gate,t.durable_payload,t.required_capabilities,t.resource_scope)::text,'UTF8')),'hex'),1,24);
    token:='GO-JARVIS-THIN-'||upper(substr(encode(sha256(convert_to(did,'UTF8')),'hex'),1,24));
    insert into public.dufynd_human_decisions(decision_id,action_type,title,question,status,decision_token,context)
    values(did,gate,'Owner gate: '||t.title,'Exact approval response: '||token,'pending',token,
     jsonb_build_object('task_id',t.task_id,'reason',gate,'risk','Action exceeds the certified free worker contract; no action executed.','cost_usd',case when t.budget_class='free' then 0 else null end,'cost_status',case when t.budget_class='free' then 'zero' else 'unknown_requires_scoped_quote' end,'benefit',t.title,'exact_go_answer',token,'live_head',ci->>'sha','gate_action_executed',false,'approval_alone_enables_execution',false)) on conflict(decision_id) do nothing;
    insert into public.dufynd_jarvis_inbox(event_type,source_type,source_id,payload,status,fingerprint,related_task_ids,processed_at)
    select 'jarvis.owner_gate','thin_v1',did,jsonb_build_object('decision_id',did,'decision_token',token,'task_id',t.task_id),'done',encode(sha256(convert_to(did,'UTF8')),'hex'),jsonb_build_array(t.task_id),now()
    where not exists(select 1 from public.dufynd_jarvis_inbox where source_type='thin_v1' and source_id=did);
    reason:='owner_gate'; exit;
   end if;
   -- Prevent dependency-event -> prepare -> claim recursion during this selection.
   perform set_config('dufynd.event_processing','true',true);
   p:=public.prepare_dufynd_execution(t.task_id,'thin-v1:'||t.task_id,'supervisor',t.resource_scope,t.durable_payload,t.durability_policy);
   perform set_config('dufynd.event_processing','',true);
   if p->>'allowed' is distinct from 'true' then result:=result||jsonb_build_array(jsonb_build_object('task_id',t.task_id,'status','no_safe_work','reason',p->>'reason')); reason:='no_safe_work'; exit; end if;
   select * into e from public.dufynd_execution_runs where execution_id=(p->'execution'->>'execution_id')::uuid for update;
   -- No fake Actions identity. Only the already-certified SQL audit may run inline.
   if e.handler_id='supervisor_state_audit' and e.status='dispatch_pending' and public.dufynd_execution_contract_valid(e.execution_id) then
    perform set_config('dufynd.execution_write','supervisor',true); perform set_config('dufynd.worker_write',e.lease_token::text,true);
    update public.dufynd_execution_runs set status='running',worker_type='deterministic_supervisor',worker_id='supervisor_v2',started_at=now(),heartbeat_at=now(),last_progress_at=now(),lease_expires_at=now()+interval '180 seconds',
     evidence=evidence||jsonb_build_array(jsonb_build_object('event','thin_v1_selected','at',now(),'live_head',ci->>'sha','ci_run_id',ci->>'run_id','paid_calls',0),jsonb_build_object('event','certified_supervisor_dispatch','at',now(),'chat_ownership',false)) where execution_id=e.execution_id;
    update public.dufynd_autonomy_tasks set worker_state='working',worker_owner='supervisor_v2',heartbeat_at=now(),last_progress_at=now(),lease_expires_at=now()+interval '180 seconds' where task_id=t.task_id;
    perform set_config('dufynd.worker_write','',true); perform set_config('dufynd.execution_write','',true);
    perform public.checkpoint_dufynd_execution(e.execution_id,e.lease_token,'supervisor_v2',1);
    if not public.finish_dufynd_execution(e.execution_id,e.lease_token,'supervisor_v2') then reason:='waiting_external'; exit; end if;
   else result:=result||jsonb_build_array(jsonb_build_object('task_id',t.task_id,'status','waiting_external','execution_status',e.status,'handler_id',e.handler_id,'contract_valid',public.dufynd_execution_contract_valid(e.execution_id))); reason:='waiting_external'; exit; end if;
   result:=result||jsonb_build_array(jsonb_build_object('task_id',t.task_id,'execution_id',e.execution_id,'status','completed'));
   reason:='no_safe_work';
  end loop;
  if i=4 and jsonb_array_length(result)=4 then reason:='bounded_limit'; end if;
 end if;
 if reason='no_safe_work' and exists(select 1 from public.dufynd_autonomy_tasks where status='waiting_external') then reason:='waiting_external'; end if;
 report:=public.read_dufynd_thin_state()||jsonb_build_object('completed',result,'stop_reason',reason,'loop_ci',ci,'paid_calls',0,'owner_gate_action_executed',false);
 insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
 values('jarvis.thin_v1.status','jarvis',report,100,now()) on conflict(key) do update set value=excluded.value,last_verified_at=excluded.last_verified_at;
 return report;
end $$;

revoke all on function public.dufynd_thin_gate(jsonb),public.poll_dufynd_thin_ci(),public.read_dufynd_thin_state(),public.read_dufynd_supervisor_audit_pre_thin(),public.read_dufynd_supervisor_audit(),public.run_dufynd_thin_v1() from public,anon,authenticated;
grant execute on function public.dufynd_thin_gate(jsonb),public.poll_dufynd_thin_ci(),public.read_dufynd_thin_state(),public.read_dufynd_supervisor_audit_pre_thin(),public.read_dufynd_supervisor_audit(),public.run_dufynd_thin_v1() to service_role;

-- Existing database wakeup, separate from the recovery job; no new service.
select cron.schedule('dufynd-thin-v1-free','1-59/2 * * * *','select public.run_dufynd_thin_v1();');
