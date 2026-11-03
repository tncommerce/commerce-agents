-- DUFYND OPS / reversible, no extra provider cost.
-- Stop synthetic half-hour tasks; keep thin CI, purchase, owner-gate and execution paths.
-- Rollback is a single feature-flag change to periodic_health_tasks=true.

CREATE OR REPLACE FUNCTION public.run_dufynd_thin_v1()
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
declare ci jsonb; t public.dufynd_autonomy_tasks; e public.dufynd_execution_runs; p jsonb;
 result jsonb:='[]'; reason text:='no_safe_work'; gate text; token text; did text; report jsonb; tid text; i int;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 if not coalesce((select value->>'enabled'='true' from public.dufynd_master_status where key='jarvis.thin_v1.config'),false) then
  return jsonb_build_object('stop_reason','disabled','paid_calls',0); end if;
 ci:=public.poll_dufynd_thin_ci();
 if ci->>'ready' is distinct from 'true' then reason:='waiting_external';
 else
  -- This is optional auditing, not an externally evidenced business event.
  -- Default to no synthetic half-hour task; keep CI and real work dispatch intact.
  if coalesce((select value->>'periodic_health_tasks'='true' from public.dufynd_master_status where key='jarvis.thin_v1.config'),false) then
  -- One meaningful metadata audit per 30-minute slot, never synthetic busywork.
  tid:='thin-health:'||to_char(now() at time zone 'UTC','YYYYMMDDHH24')||case when extract(minute from now())<30 then '00' else '30' end;
  insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,priority,budget_class,resource_scope,durability_policy,durable_payload)
  values(tid,'supervisor','Free First-Money and supervisor health audit','Persist metadata evidence only.','ready',100,'free','["db:jarvis.supervisor_v2.health"]','durable','{"kind":"supervisor_state_audit","steps":1,"interval_seconds":2}') on conflict(task_id) do nothing;
  end if;
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
 
 report:=public.read_dufynd_thin_state()||jsonb_build_object('completed',result,'stop_reason',reason,'planner',public.read_dufynd_planner_state(),'loop_ci',ci,'paid_calls',0,'owner_gate_action_executed',false);
 insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
 values('jarvis.thin_v1.status','jarvis',report,100,now()) on conflict(key) do update set value=excluded.value,last_verified_at=excluded.last_verified_at;
 return report;
end $function$;

update public.dufynd_master_status
set value=jsonb_set(value,'{periodic_health_tasks}','false'::jsonb,true),last_verified_at=now()
where key='jarvis.thin_v1.config';

revoke all on function public.run_dufynd_thin_v1() from public,anon,authenticated;
grant execute on function public.run_dufynd_thin_v1() to service_role;
