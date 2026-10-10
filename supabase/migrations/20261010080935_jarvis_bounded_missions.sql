-- One bounded mission on the existing task/worker plane; no new platform or model.
-- A tick commits one real handler result and its checkpoint atomically.
create function public.start_dufynd_mission_v1(p_id text,p_goal text)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare k text; m jsonb; active jsonb;
begin
 if p_id is null or p_id !~ '^[a-z0-9_]{1,64}$'
 or p_goal is distinct from 'zero_budget_content_preparation' then
  raise exception 'unsupported bounded mission';
 end if;
 perform pg_advisory_xact_lock(hashtext('dufynd-missions-v1'));
 k := 'jarvis.mission.v1:'||p_id;
 select value into m from public.dufynd_master_status where key=k;
 if m is not null then return m; end if;
 select value into active from public.dufynd_master_status
 where key like 'jarvis.mission.v1:%' and value->>'goal'=p_goal
 and value->>'state' in ('ready','retry_wait','waiting_lease') limit 1;
 if active is not null then return active; end if;
 m := jsonb_build_object('version',1,'mission_id',p_id,'goal',p_goal,
  'business_goal','Prepare the next zero-budget reach-content brief from current evidence; no generation or publication.',
  'state','ready','step',1,'attempts',0,'created_at',now(),'updated_at',now(),
  'plan',jsonb_build_array(
   jsonb_build_object('step',1,'handler','content_backlog_prioritize','output','ranked_now_hold_pause_queue'),
   jsonb_build_object('step',2,'handler','content_production_packet','depends_on',1,'output','idea_bound_production_brief')),
  'checkpoints','[]'::jsonb,'paid_calls',0,'new_spend_usd',0,
  'next_step','Execute and verify the backlog worker.');
 insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
 values(k,'jarvis',m,100,now());
 return m;
end $$;
revoke all on function public.start_dufynd_mission_v1(text,text) from public,anon,authenticated;
grant execute on function public.start_dufynd_mission_v1(text,text) to service_role,postgres;

create function public.tick_dufynd_mission_v1()
returns jsonb language plpgsql security invoker set search_path=public as $$
declare
 k text; m jsonb; step integer; tid text; hid text; worker text; resources jsonb;
 h public.dufynd_handler_contracts; t public.dufynd_autonomy_tasks;
 artifact jsonb; first_result jsonb; result_key text; result jsonb; result_hash text;
 packet jsonb; outcome jsonb; prefix text; idea text; attempts integer; reason text;
begin
 if not pg_try_advisory_xact_lock(hashtext('dufynd-missions-v1')) then
  return jsonb_build_object('state','busy','paid_calls',0);
 end if;
 select key,value into k,m from public.dufynd_master_status
 where key like 'jarvis.mission.v1:%'
 and value->>'state' in ('ready','retry_wait','waiting_lease')
 order by last_verified_at,key limit 1 for update skip locked;
 if k is null then return jsonb_build_object('state','idle','paid_calls',0); end if;
 if public.dufynd_parse_timestamp(m->>'next_retry_at')>now() then return m; end if;
 step := (m->>'step')::integer;
 if m->>'goal' is distinct from 'zero_budget_content_preparation' or step not in (1,2) then
  raise exception 'invalid mission checkpoint';
 end if;
 hid := case step when 1 then 'content_backlog_prioritize' else 'content_production_packet' end;
 worker := case step when 1 then 'content_backlog_worker_v1' else 'content_packet_worker_v1' end;
 resources := case step when 1 then '["db:dufynd.content_ideas","db:dufynd.zero_budget_queue"]'::jsonb
  else '["db:dufynd.content_ideas","db:dufynd.zero_budget_queue","db:dufynd.content_packet"]'::jsonb end;
 -- Match the existing workers' lock order before checking resource leases.
 perform pg_advisory_xact_lock(hashtext(case step when 1 then 'dufynd-content-backlog-worker-v1' else 'dufynd-content-packet-worker-v1' end));
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 tid := 'mission:v1:'||(m->>'mission_id')||':'||step;
 result_key := 'jarvis.mission_result.v1:'||(m->>'mission_id')||':'||step;
 select * into h from public.dufynd_handler_contracts where handler_id=hid and handler_version='1';
 if h.handler_id is null or not h.enabled
 or h.contract->>'certification_status' is distinct from 'certified'
 or h.contract->>'cost_class' is distinct from 'free'
 or (resources <@ (h.contract->'allowed_resources')) is not true then
  reason := 'handler_not_certified_free';
 elsif exists(select 1 from public.dufynd_autonomy_tasks q where q.task_id<>tid
  and q.released_at is null and q.lease_expires_at>now()
  and q.worker_state in ('claimed','working','verifying')
  and public.dufynd_resources_conflict(resources,q.resource_scope)) then
  m := m || jsonb_build_object('state','waiting_lease','next_retry_at',now()+interval '2 minutes',
   'next_step','Wait for the existing resource lease; do not steal work.','updated_at',now());
  update public.dufynd_master_status set value=m,last_verified_at=now() where key=k;
  return m;
 end if;
 if reason is not null then
  m := m||jsonb_build_object('state','blocked','last_error',reason,'updated_at',now(),
   'next_step','Inspect the existing handler certification and free resource contract before starting a new mission.');
 else
  -- Exceptions roll back this whole step, including leases and handler writes.
  -- The outer checkpoint survives and schedules a bounded retry.
  begin
   packet := jsonb_build_object('kind',hid,'version',1);
   if step=2 then
    select value->'artifact' into first_result from public.dufynd_master_status
    where key='jarvis.mission_result.v1:'||(m->>'mission_id')||':1';
    idea := first_result#>>'{next_content_move,idea_id}';
    if idea is null or not exists(select 1 from public.dufynd_autonomy_tasks
     where task_id='mission:v1:'||(m->>'mission_id')||':1' and status='done') then
     raise exception using errcode='P1002',message='missing verified predecessor';
    end if;
    packet := packet||jsonb_build_object('idea_id',idea);
   end if;
   -- Create only the next task, inside its execution transaction. No orphan ready
   -- task can escape contract checks through another independently scheduled worker.
   insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,priority,
    budget_class,resource_scope,durability_policy,durable_payload,dependencies,
    required_capabilities,forbidden_actions)
   values(tid,'content','Mission '||(m->>'mission_id')||' step '||step,
    'Execute the fixed certified internal handler and preserve the full verified result. No media generation or publication.',
    'ready',100,'free',resources,'durable',packet,
    case step when 1 then '[]'::jsonb else jsonb_build_array('mission:v1:'||(m->>'mission_id')||':1') end,
    h.contract->'required_capabilities',h.contract->'forbidden_actions')
   on conflict(task_id) do nothing;
   select * into t from public.dufynd_autonomy_tasks where task_id=tid;
   if t.durable_payload is distinct from packet or t.resource_scope is distinct from resources
    or t.budget_class<>'free' or t.provider_cost_unknown or t.requires_human_approval
    or t.external_review_required or t.needs_freshness_recheck then
    raise exception using errcode='P1003',message='mission task contract changed';
   end if;
   if t.status<>'done' then
    if step=1 then outcome:=public.run_dufynd_content_backlog_worker_v1();
    else outcome:=public.run_dufynd_content_packet_worker_v1(); end if;
    if outcome->>'task_id' is distinct from tid or outcome->>'status' is distinct from 'completed' then
     raise exception using errcode='P1004',message='worker did not complete exact mission task';
    end if;
   end if;
   select * into t from public.dufynd_autonomy_tasks where task_id=tid;
   prefix:=case step when 1 then 'Zero-budget content queue: ' else 'Zero-budget production packet: ' end;
   if t.status<>'done' or t.worker_state<>'done' or t.worker_owner is distinct from worker
    or t.lease_token is null or t.released_at is null or t.lease_expires_at>now()
    or not starts_with(coalesce(t.evidence,''),prefix) then
    raise exception using errcode='P1005',message='durable result or released lease missing';
   end if;
   artifact:=substring(t.evidence from length(prefix)+1)::jsonb;
   if artifact->'publishing_allowed' is distinct from 'false'::jsonb
    or artifact->'new_spend_usd' is distinct from '0'::jsonb
    or public.dufynd_parse_timestamp(artifact->>'observed_at') is null
    or public.dufynd_parse_timestamp(artifact->>'observed_at')<(m->>'created_at')::timestamptz then
    raise exception using errcode='P1005',message='artifact safety or freshness failed';
   end if;
   if step=1 and (jsonb_typeof(artifact->'now') is distinct from 'array'
    or coalesce(jsonb_array_length(artifact->'now'),0)=0
    or artifact#>>'{next_content_move,idea_id}' is null) then
    raise exception using errcode='P1002',message='no eligible source candidate';
   end if;
   if step=2 and (artifact->>'idea_id' is distinct from idea
    or artifact->'paid_generation_allowed' is distinct from 'false'::jsonb
    or artifact#>'{qa,target_score}' is distinct from '9.5'::jsonb
    or nullif(artifact->>'concept','') is null
    or jsonb_typeof(artifact->'hard_gates') is distinct from 'array') then
    raise exception using errcode='P1005',message='idea-bound production brief QC failed';
   end if;
   result_hash:=md5(artifact::text);
   result:=jsonb_build_object('mission_id',m->>'mission_id','step',step,'task_id',tid,
    'handler',hid,'worker',worker,'completed_at',now(),'lease_released',true,
    'artifact',artifact,'artifact_md5',result_hash,'quality_verified',true);
   insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
   values(result_key,'jarvis',result,100,now()) on conflict(key) do nothing;
   if not exists(select 1 from public.dufynd_master_status where key=result_key
    and value->>'artifact_md5'=result_hash and value->>'task_id'=tid) then
    raise exception using errcode='P1005',message='immutable result conflict';
   end if;
   m := (m-array['next_retry_at','last_error'])||jsonb_build_object(
    'state',case step when 2 then 'completed' else 'ready' end,'step',step+1,'attempts',0,
    'updated_at',now(),'checkpoints',(m->'checkpoints')||jsonb_build_array((result-'artifact')||jsonb_build_object('artifact_key',result_key)),
    'next_step',case step when 1 then 'Build the production brief for the exact selected idea.'
     else 'Internal preparation complete. Select or create the visual and perform fresh 9.5 QA; publication remains gated.' end);
  exception when others then
   attempts:=coalesce((m->>'attempts')::integer,0)+1;
   m:=m||jsonb_build_object('state',case when attempts>=3 or sqlstate in ('P1002','P1003','P1005')
      then 'blocked' else 'retry_wait' end,
    'attempts',attempts,'last_error','step_failed_'||sqlstate,'updated_at',now(),
    'next_retry_at',now()+make_interval(secs=>120*attempts),
    'next_step','Inspect the bounded failure code; previous verified checkpoints are retained.');
  end;
 end if;
 update public.dufynd_master_status set value=m,last_verified_at=now() where key=k;
 if m->>'state' in ('blocked','retry_wait') then
  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.mission_alert.v1:'||(m->>'mission_id'),'ops',
   jsonb_build_object('mission_id',m->>'mission_id','state',m->>'state','reason',m->>'last_error',
    'first_seen_at',now(),'action',m->>'next_step','email_sent',false),100,now())
  on conflict(key) do update set value=excluded.value||jsonb_build_object(
   'first_seen_at',dufynd_master_status.value->'first_seen_at'),last_verified_at=excluded.last_verified_at;
 elsif m->>'state'='completed' then
  update public.dufynd_master_status set value=value||jsonb_build_object('state','resolved','resolved_at',now())
  where key='jarvis.mission_alert.v1:'||(m->>'mission_id');
 end if;
 return m;
end $$;
revoke all on function public.tick_dufynd_mission_v1() from public,anon,authenticated;
grant execute on function public.tick_dufynd_mission_v1() to service_role,postgres;

create function public.run_dufynd_ceo_with_missions_v1()
returns jsonb language plpgsql security invoker set search_path=public as $$
declare m jsonb;
begin
 m:=public.tick_dufynd_mission_v1();
 if m->>'state'='idle' then return public.run_dufynd_ceo_safe_cycle_v1(); end if;
 return m;
end $$;
revoke all on function public.run_dufynd_ceo_with_missions_v1() from public,anon,authenticated;
grant execute on function public.run_dufynd_ceo_with_missions_v1() to service_role,postgres;

-- Preserve the existing frequency, eleven jobs and all independent safe workers.
do $$ declare j bigint; begin
 if to_regclass('cron.job') is not null then
  select jobid into j from cron.job where jobname='dufynd-ceo-v2-growth-loop';
  if j is not null then perform cron.alter_job(j,command:='select public.run_dufynd_ceo_with_missions_v1();'); end if;
 end if;
end $$;
