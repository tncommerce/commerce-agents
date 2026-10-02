-- One execution identity attached to existing autonomy tasks, not a second queue.
alter table public.dufynd_autonomy_tasks add column durability_policy text not null default 'interactive'
 check (durability_policy in ('interactive','durable','condition_watch'));
create table public.dufynd_execution_runs (
 execution_id uuid primary key default gen_random_uuid(),
 task_id text not null references public.dufynd_autonomy_tasks(task_id),
 idempotency_key text not null unique check(length(idempotency_key) between 1 and 200),
 request_hash text not null,
 worker_type text not null default 'github_actions' check(worker_type in ('github_actions','render_worker','deterministic_supervisor','bounded_ai_worker')),
 worker_id text, external_run_id text,
 status text not null default 'dispatch_pending' check(status in ('dispatch_pending','dispatched','running','verifying','completed','retryable','waiting_external','waiting_human','failed_terminal','stale')),
 attempt int not null default 1 check(attempt between 1 and 3),
 scope text not null, resources jsonb not null check(public.dufynd_valid_resource_scope(resources)),
 lease_token uuid not null, lease_expires_at timestamptz not null,
 durability_policy text not null check(durability_policy in ('interactive','durable','condition_watch')),
 payload jsonb not null, created_at timestamptz not null default now(),
 started_at timestamptz, heartbeat_at timestamptz, last_progress_at timestamptz,
 last_checkpoint jsonb not null default '{"step":0,"sum":0}', completed_at timestamptz,
 recovery_count int not null default 0, last_error text, evidence jsonb not null default '[]',
 external_checked_at timestamptz, external_observation jsonb,
 observer_request_id bigint, observer_requested_at timestamptz
);
create unique index dufynd_execution_one_active_task on public.dufynd_execution_runs(task_id)
 where status not in ('completed','failed_terminal');
create index dufynd_execution_observation on public.dufynd_execution_runs(status,external_checked_at);
alter table public.dufynd_execution_runs enable row level security;
revoke all on public.dufynd_execution_runs from public,anon,authenticated;
grant all on public.dufynd_execution_runs to service_role;

create function public.guard_dufynd_execution_run() returns trigger
language plpgsql security invoker set search_path=public as $$
begin
 if coalesce(current_setting('dufynd.execution_write',true),'') not in (old.execution_id::text,'supervisor') then
  raise exception 'execution mutations require fenced RPC';
 end if;
 return new;
end $$;
create trigger dufynd_execution_guard before update on public.dufynd_execution_runs
 for each row execute function public.guard_dufynd_execution_run();
create function public.guard_dufynd_execution_task() returns trigger
language plpgsql security invoker set search_path=public as $$
declare eid uuid;
begin
 select execution_id into eid from public.dufynd_execution_runs where task_id=old.task_id and status not in ('completed','failed_terminal');
 if eid is not null and coalesce(current_setting('dufynd.execution_write',true),'') not in (eid::text,'supervisor')
 and coalesce(current_setting('dufynd.worker_write',true),'')<>'supervisor' then
  raise exception 'durable task requires execution RPC';
 end if;
 return new;
end $$;
create trigger dufynd_execution_task_guard before update on public.dufynd_autonomy_tasks
 for each row execute function public.guard_dufynd_execution_task();

create function public.prepare_dufynd_execution(p_task_id text,p_idempotency_key text,p_scope text,p_resources jsonb,p_payload jsonb,p_policy text default 'durable')
returns jsonb language plpgsql security invoker set search_path=public as $$
declare e public.dufynd_execution_runs; t public.dufynd_autonomy_tasks; token uuid:=gen_random_uuid(); fingerprint text; claimed jsonb;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 -- A deliberately small, free handler allowlist. No arbitrary command/model executes.
 if nullif(p_task_id,'') is null or nullif(p_idempotency_key,'') is null or length(p_idempotency_key)>200
 or nullif(p_scope,'') is null or not public.dufynd_valid_resource_scope(p_resources)
 or p_policy not in ('interactive','durable','condition_watch')
 or jsonb_typeof(p_payload) is distinct from 'object'
 or jsonb_typeof(p_payload->'steps') is distinct from 'number'
 or jsonb_typeof(p_payload->'interval_seconds') is distinct from 'number'
 or p_payload->>'kind' is distinct from 'durability_probe'
 or p_payload - array['kind','steps','interval_seconds'] <> '{}'::jsonb
 or coalesce(p_payload->>'steps','') !~ '^[0-9]{1,2}$'
 or coalesce(p_payload->>'interval_seconds','') !~ '^[0-9]{1,2}$' then
  return jsonb_build_object('allowed',false,'reason','uncertified_free_handler');
 end if;
 if (p_payload->>'steps')::int not between 1 and 30 or (p_payload->>'interval_seconds')::int not between 2 and 30 then
  return jsonb_build_object('allowed',false,'reason','invalid_probe_limits');
 end if;
 fingerprint:=encode(sha256(convert_to(jsonb_build_array(p_task_id,p_scope,p_resources,p_payload,p_policy)::text,'UTF8')),'hex');
 select * into e from public.dufynd_execution_runs where idempotency_key=p_idempotency_key;
 if found then
  if e.request_hash<>fingerprint then return jsonb_build_object('allowed',false,'reason','idempotency_conflict'); end if;
  return jsonb_build_object('allowed',true,'reused',true,'execution',to_jsonb(e));
 end if;
 if exists(select 1 from public.dufynd_execution_runs where task_id=p_task_id and status not in ('completed','failed_terminal')) then
  return jsonb_build_object('allowed',false,'reason','task_already_executing');
 end if;
 insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,requires_human_approval,dependencies,budget_class,resource_scope,durability_policy)
 values(p_task_id,'supervisor','Durable deterministic verification','Execute the certified free durability probe only.','ready',false,'[]','free',p_resources,p_policy)
 on conflict(task_id) do nothing;
 select * into t from public.dufynd_autonomy_tasks where task_id=p_task_id;
 if t.budget_class<>'free' or t.provider_cost_unknown or t.resource_scope<>p_resources or t.durability_policy<>p_policy then
  return jsonb_build_object('allowed',false,'reason','task_contract_conflict');
 end if;
 claimed:=public.claim_dufynd_worker_v2(p_task_id,'durable_handoff',token);
 if claimed is null then return jsonb_build_object('allowed',false,'reason','scope_or_task_unavailable'); end if;
 perform set_config('dufynd.worker_write',token::text,true);
 update public.dufynd_autonomy_tasks set lease_expires_at=now()+interval '15 minutes' where task_id=p_task_id;
 insert into public.dufynd_execution_runs(task_id,idempotency_key,request_hash,scope,resources,lease_token,lease_expires_at,payload,durability_policy,evidence)
 values(p_task_id,p_idempotency_key,fingerprint,p_scope,p_resources,token,now()+interval '15 minutes',p_payload,p_policy,
 jsonb_build_array(jsonb_build_object('event','durable_handoff_persisted','at',now(),'chat_ownership',false))) returning * into e;
 perform set_config('dufynd.worker_write','',true);
 return jsonb_build_object('allowed',true,'reused',false,'execution',to_jsonb(e));
end $$;

create function public.take_dufynd_execution(p_external_run_id text,p_worker_id text,p_execution_id uuid default null)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare e public.dufynd_execution_runs; t public.dufynd_autonomy_tasks;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 if coalesce(p_external_run_id,'') !~ '^[0-9]+$' or nullif(p_worker_id,'') is null then return null; end if;
 select * into e from public.dufynd_execution_runs where status='dispatch_pending' and worker_type='github_actions'
 and (p_execution_id is null or execution_id=p_execution_id) order by created_at limit 1 for update;
 if not found or e.lease_expires_at<=now() then return null; end if;
 select * into t from public.dufynd_autonomy_tasks where task_id=e.task_id for update;
 if t.lease_token is distinct from e.lease_token or t.released_at is not null or t.budget_class<>'free'
 or t.lease_expires_at<=now() or e.payload->>'kind'<>'durability_probe' then return null; end if;
 perform set_config('dufynd.execution_write',e.execution_id::text,true);
 perform set_config('dufynd.worker_write',e.lease_token::text,true);
 update public.dufynd_execution_runs set status='dispatched',external_run_id=p_external_run_id,worker_id=p_worker_id,
 started_at=coalesce(started_at,now()),heartbeat_at=now(),last_progress_at=now(),lease_expires_at=now()+interval '180 seconds',
 evidence=evidence||jsonb_build_array(jsonb_build_object('event','external_dispatch_bound','at',now(),'run_id',p_external_run_id,'worker_id',p_worker_id,'attempt',attempt))
 where execution_id=e.execution_id returning * into e;
 update public.dufynd_autonomy_tasks set worker_owner=p_worker_id,worker_state='working',heartbeat_at=now(),last_progress_at=now(),lease_expires_at=e.lease_expires_at where task_id=e.task_id;
 perform set_config('dufynd.worker_write','',true); perform set_config('dufynd.execution_write','',true);
 return to_jsonb(e);
end $$;

create function public.checkpoint_dufynd_execution(p_execution_id uuid,p_token uuid,p_worker_id text,p_step int default null)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare e public.dufynd_execution_runs; t public.dufynd_autonomy_tasks; current_step int; destination text;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 select * into e from public.dufynd_execution_runs where execution_id=p_execution_id for update;
 if not found or e.lease_token is distinct from p_token or e.worker_id is distinct from p_worker_id
 or e.status not in ('dispatched','running') or e.lease_expires_at<=now() then return null; end if;
 select * into t from public.dufynd_autonomy_tasks where task_id=e.task_id for update;
 if t.lease_token is distinct from p_token or t.released_at is not null or t.lease_expires_at<=now() then return null; end if;
 current_step:=(e.last_checkpoint->>'step')::int;
 if p_step is not null and p_step<>current_step and (p_step<>current_step+1 or p_step>(e.payload->>'steps')::int) then return null; end if;
 if e.last_progress_at<now()-interval '600 seconds' then return null; end if;
 destination:=case when coalesce(p_step,current_step)=(e.payload->>'steps')::int then 'verifying' else 'running' end;
 perform set_config('dufynd.execution_write',e.execution_id::text,true); perform set_config('dufynd.worker_write',p_token::text,true);
 update public.dufynd_execution_runs set status=destination,heartbeat_at=now(),lease_expires_at=now()+interval '180 seconds',
 last_progress_at=case when p_step>current_step then now() else last_progress_at end,
 last_checkpoint=case when p_step>current_step then jsonb_build_object('step',p_step,'sum',p_step*(p_step+1)/2,'verified',p_step=(payload->>'steps')::int,'verified_at',now()) else last_checkpoint end,
 evidence=case when p_step>current_step then evidence||jsonb_build_array(jsonb_build_object('event','progress','step',p_step,'at',now(),'worker_id',p_worker_id,'attempt',attempt)) else evidence end
 where execution_id=e.execution_id returning * into e;
 update public.dufynd_autonomy_tasks set worker_state=case when destination='verifying' then 'verifying' else 'working' end,heartbeat_at=now(),last_progress_at=e.last_progress_at,lease_expires_at=e.lease_expires_at,
 expected_next_checkpoint='durable_execution:'||e.execution_id::text||':step:'||(coalesce(p_step,current_step)+1)::text where task_id=e.task_id;
 perform set_config('dufynd.worker_write','',true); perform set_config('dufynd.execution_write','',true);
 return to_jsonb(e);
end $$;

create function public.finish_dufynd_execution(p_execution_id uuid,p_token uuid,p_worker_id text)
returns boolean language plpgsql security invoker set search_path=public as $$
declare e public.dufynd_execution_runs; t public.dufynd_autonomy_tasks; n int;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 select * into e from public.dufynd_execution_runs where execution_id=p_execution_id for update;
 if not found or e.lease_token is distinct from p_token or e.worker_id is distinct from p_worker_id then return false; end if;
 if e.status='completed' then return true; end if;
 select * into t from public.dufynd_autonomy_tasks where task_id=e.task_id for update;
 if t.lease_token is distinct from p_token or t.released_at is not null then return false; end if;
 if (e.lease_expires_at<=now() or t.lease_expires_at<=now()) and coalesce(current_setting('dufynd.execution_write',true),'')<>'supervisor' then return false; end if;
 n:=(e.payload->>'steps')::int;
 if e.status<>'verifying' or e.last_checkpoint->>'verified' is distinct from 'true'
 or (e.last_checkpoint->>'step')::int<>n or (e.last_checkpoint->>'sum')::int<>n*(n+1)/2 then return false; end if;
 -- Verification is the SQL-derived recipe result, never success prose or exit code.
 perform set_config('dufynd.execution_write',e.execution_id::text,true); perform set_config('dufynd.worker_write',p_token::text,true);
 update public.dufynd_autonomy_tasks set status='done',worker_state='done',evidence='Durable execution '||e.execution_id::text||' verified checkpoint '||e.last_checkpoint::text,
 released_at=now(),lease_expires_at=now(),expected_next_checkpoint=null,blocked_reason=null where task_id=e.task_id;
 update public.dufynd_execution_runs set status='completed',completed_at=now(),lease_expires_at=now(),
 evidence=evidence||jsonb_build_array(jsonb_build_object('event','verified_completed','at',now(),'worker_id',p_worker_id,'external_run_id',external_run_id,'chat_ownership',false)) where execution_id=e.execution_id;
 perform set_config('dufynd.worker_write','',true); perform set_config('dufynd.execution_write','',true);
 return true;
end $$;

create function public.observe_dufynd_execution(p_execution_id uuid,p_external_run_id text,p_observation jsonb)
returns boolean language plpgsql security invoker set search_path=public as $$
declare e public.dufynd_execution_runs;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 select * into e from public.dufynd_execution_runs where execution_id=p_execution_id for update;
 if not found or e.external_run_id is distinct from p_external_run_id or e.status in ('completed','failed_terminal') then return false; end if;
 if coalesce(p_observation->>'state','') not in ('queued','running','success','failure','missing','unknown') then return false; end if;
 perform set_config('dufynd.execution_write',e.execution_id::text,true);
 update public.dufynd_execution_runs set external_checked_at=now(),external_observation=p_observation,
 observer_request_id=null,observer_requested_at=null where execution_id=e.execution_id;
 perform set_config('dufynd.execution_write','',true);
 return true;
end $$;

create function public.fail_dufynd_execution(p_execution_id uuid,p_token uuid,p_worker_id text,p_error text)
returns boolean language plpgsql security invoker set search_path=public as $$
declare e public.dufynd_execution_runs;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 select * into e from public.dufynd_execution_runs where execution_id=p_execution_id for update;
 if not found or e.lease_token is distinct from p_token or e.worker_id is distinct from p_worker_id or e.status not in ('dispatched','running') then return false; end if;
 perform set_config('dufynd.execution_write',e.execution_id::text,true);
 update public.dufynd_execution_runs set status='stale',last_error=left(p_error,1000) where execution_id=e.execution_id;
 perform set_config('dufynd.execution_write','',true);
 return true;
end $$;

create function public.reconcile_dufynd_executions()
returns jsonb language plpgsql security invoker set search_path=public as $$
declare e public.dufynd_execution_runs; t public.dufynd_autonomy_tasks; findings jsonb:='[]'; reason text; token uuid; destination text; step int;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 for e in select * from public.dufynd_execution_runs where status not in ('completed','failed_terminal','waiting_human','waiting_external') order by created_at for update loop
  select * into t from public.dufynd_autonomy_tasks where task_id=e.task_id for update;
  if t.lease_token is distinct from e.lease_token or t.released_at is not null then
   perform set_config('dufynd.execution_write','supervisor',true);
   update public.dufynd_execution_runs set status='failed_terminal',last_error='task_fence_superseded',completed_at=now() where execution_id=e.execution_id;
   findings:=findings||jsonb_build_array(jsonb_build_object('id',e.execution_id,'reason','task_fence_superseded')); continue;
  end if;
  perform set_config('dufynd.execution_write','supervisor',true);
  if e.status='verifying' and public.finish_dufynd_execution(e.execution_id,e.lease_token,e.worker_id) then
   findings:=findings||jsonb_build_array(jsonb_build_object('id',e.execution_id,'event','finalization_recovered')); continue;
  end if;
  -- Handoff owns a bounded queue lease, never a chat lease. Keep Phase-1
  -- reconciliation from confusing queued dispatch with a silent worker.
  if e.status='dispatch_pending' and e.lease_expires_at>now() then
   perform set_config('dufynd.execution_write','supervisor',true); perform set_config('dufynd.worker_write','supervisor',true);
   update public.dufynd_autonomy_tasks set heartbeat_at=now(),last_progress_at=now() where task_id=e.task_id;
   continue;
  end if;
  reason:=case when e.status='stale' then coalesce(e.last_error,'worker_failure')
    when e.status='retryable' then null
    when e.external_observation->>'state'='missing' then 'external_run_missing'
    when e.external_observation->>'state'='failure' then 'external_run_failed'
    when e.external_observation->>'state'='success' then 'external_success_without_verified_result'
    when e.lease_expires_at<=now() or t.lease_expires_at<=now() then 'lease_expired'
    when e.heartbeat_at<now()-interval '180 seconds' then 'heartbeat_stale'
    when e.last_progress_at<now()-interval '600 seconds' then 'progress_stalled' else null end;
  if reason is not null then
   token:=gen_random_uuid(); destination:=case when e.attempt>=3 then 'failed_terminal' else 'retryable' end;
   perform set_config('dufynd.execution_write','supervisor',true); perform set_config('dufynd.worker_write','supervisor',true);
   update public.dufynd_execution_runs set status=destination,last_error=reason,recovery_count=recovery_count+1,
    lease_token=token,lease_expires_at=now()+interval '180 seconds',worker_id=null,
    evidence=evidence||jsonb_build_array(jsonb_build_object('event','fenced_recovery','at',now(),'reason',reason,'prior_external_run_id',external_run_id,'prior_worker_id',worker_id,'attempt',attempt)),external_run_id=null,external_observation=null,observer_request_id=null,
    completed_at=case when destination='failed_terminal' then now() else null end where execution_id=e.execution_id;
   update public.dufynd_autonomy_tasks set lease_token=token,worker_owner='durable_recovery',lease_expires_at=case when destination='failed_terminal' then now() else now()+interval '180 seconds' end,
    released_at=case when destination='failed_terminal' then now() else null end,worker_state=case when destination='failed_terminal' then 'failed_terminal' else 'claimed' end,
    status=case when destination='failed_terminal' then 'blocked' else 'in_progress' end,heartbeat_at=now(),last_progress_at=now(),retry_count=retry_count+1,blocked_reason=reason where task_id=e.task_id;
   findings:=findings||jsonb_build_array(jsonb_build_object('id',e.execution_id,'event',destination,'reason',reason));
   continue;
  end if;
  if e.status='retryable' then
   -- Only this certified SQL-computable free recipe can fall back to the
   -- existing autonomous watchdog. Future engineering handlers need a durable
   -- dispatch credential; never execute arbitrary instructions in SQL.
   if e.payload->>'kind'<>'durability_probe' then continue; end if;
   perform set_config('dufynd.execution_write','supervisor',true); perform set_config('dufynd.worker_write','supervisor',true);
   update public.dufynd_execution_runs set status='running',worker_type='deterministic_supervisor',worker_id='supervisor_v2',attempt=attempt+1,
    heartbeat_at=now(),last_progress_at=now(),lease_expires_at=now()+interval '180 seconds',external_checked_at=null,
    evidence=evidence||jsonb_build_array(jsonb_build_object('event','checkpoint_resumed','at',now(),'checkpoint',last_checkpoint)) where execution_id=e.execution_id returning * into e;
   update public.dufynd_autonomy_tasks set worker_owner='supervisor_v2',worker_state='working',heartbeat_at=now(),last_progress_at=now(),lease_expires_at=e.lease_expires_at where task_id=e.task_id;
  end if;
  if e.worker_type='deterministic_supervisor' and e.status='running' then
   step:=(e.last_checkpoint->>'step')::int+1;
   perform public.checkpoint_dufynd_execution(e.execution_id,e.lease_token,e.worker_id,step);
   if step=(e.payload->>'steps')::int then perform public.finish_dufynd_execution(e.execution_id,e.lease_token,e.worker_id); end if;
  end if;
 end loop;
 perform set_config('dufynd.worker_write','',true); perform set_config('dufynd.execution_write','',true);
 return jsonb_build_object('checked_at',now(),'findings',findings);
end $$;

-- Public repository read-only observer; no GitHub credential, no write call.
-- Dynamic SQL makes these functions testable on PostgreSQL without pg_net.
create function public.poll_dufynd_external_runs() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare e public.dufynd_execution_runs; r record; body jsonb; state text; request_id bigint; checked int:=0;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 if to_regnamespace('net') is null then return jsonb_build_object('available',false); end if;
 for e in select * from public.dufynd_execution_runs where external_run_id is not null and status not in ('completed','failed_terminal') and observer_request_id is not null for update loop
  execute 'select status_code,content,timed_out,error_msg from net._http_response where id=$1' into r using e.observer_request_id;
  if r.status_code is null and e.observer_requested_at>now()-interval '60 seconds' then continue; end if;
  state:='unknown'; body:='{}';
  if r.status_code=404 then state:='missing';
  elsif r.status_code=200 then
   begin
    body:=r.content::jsonb;
    if body->>'id'=e.external_run_id and body->>'head_branch'='scentai-mvp' and body->>'path'='.github/workflows/dufynd-jarvis-manual.yml' then
     state:=case when body->>'status'='completed' then case when body->>'conclusion'='success' then 'success' else 'failure' end
     when body->>'status' in ('queued','waiting','pending','requested') then 'queued' when body->>'status'='in_progress' then 'running' else 'unknown' end;
    end if;
   exception when others then state:='unknown'; end;
  end if;
  perform public.observe_dufynd_execution(e.execution_id,e.external_run_id,jsonb_build_object('state',state,'http_status',r.status_code,'status',body->>'status','conclusion',body->>'conclusion','source','github_public_api','at',now())); checked:=checked+1;
 end loop;
 -- One request per two-minute watchdog tick: <=30/hour and no idle traffic.
 select * into e from public.dufynd_execution_runs where worker_type='github_actions' and external_run_id ~ '^[0-9]+$'
 and status in ('dispatched','running','verifying') and observer_request_id is null
 and (external_checked_at is null or external_checked_at<now()-interval '120 seconds') order by external_checked_at nulls first limit 1 for update;
 if found then
  execute 'select net.http_get(url:=$1,headers:=$2,timeout_milliseconds:=5000)' into request_id
  using 'https://api.github.com/repos/tncommerce/commerce-agents/actions/runs/'||e.external_run_id,
   '{"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"DUFYND-Supervisor-V2"}'::jsonb;
  perform set_config('dufynd.execution_write',e.execution_id::text,true);
  update public.dufynd_execution_runs set observer_request_id=request_id,observer_requested_at=now() where execution_id=e.execution_id;
 end if;
 perform set_config('dufynd.execution_write','',true);
 return jsonb_build_object('available',true,'checked',checked);
end $$;

-- Extend the same autonomous watchdog entry point; preserve budget reconciliation.
alter function public.reconcile_dufynd_supervisor_v2() rename to reconcile_dufynd_supervisor_v2_phase2a;
create function public.reconcile_dufynd_supervisor_v2() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare observers jsonb; executions jsonb; workers jsonb;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 observers:=public.poll_dufynd_external_runs();
 executions:=public.reconcile_dufynd_executions();
 workers:=public.reconcile_dufynd_supervisor_v2_phase2a();
 update public.dufynd_master_status set value=value||jsonb_build_object('executions',executions,'external_observer',observers) where key='jarvis.supervisor_v2.health';
 return workers||jsonb_build_object('executions',executions,'external_observer',observers);
end $$;

-- Internal functions only. No public execution interface or exposed credentials.
do $$ declare f record; begin
 for f in select oid::regprocedure as signature from pg_proc where pronamespace='public'::regnamespace
 and proname in ('guard_dufynd_execution_run','guard_dufynd_execution_task','prepare_dufynd_execution','take_dufynd_execution','checkpoint_dufynd_execution','finish_dufynd_execution','observe_dufynd_execution','fail_dufynd_execution','reconcile_dufynd_executions','poll_dufynd_external_runs','reconcile_dufynd_supervisor_v2','reconcile_dufynd_supervisor_v2_phase2a') loop
  execute 'revoke all on function '||f.signature||' from public,anon,authenticated';
  execute 'grant execute on function '||f.signature||' to service_role';
 end loop;
end $$;

-- Hosted observer extension; CI applies the portable part above.
create extension if not exists pg_net with schema extensions;
