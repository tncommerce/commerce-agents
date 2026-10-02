-- Fixed read-only CI/PR correlation, on the existing event/packet/watchdog path.
-- No HTTP inside the handler, no approval/merge/deploy rights, no second queue.
create table public.dufynd_ci_pr_verification_evidence (
 execution_id uuid primary key references public.dufynd_execution_runs(execution_id),
 report jsonb not null, report_hash text not null check(report_hash ~ '^[a-f0-9]{64}$'),
 observed_at timestamptz not null default now()
);
alter table public.dufynd_ci_pr_verification_evidence enable row level security;
revoke all on public.dufynd_ci_pr_verification_evidence from public,anon,authenticated;
grant all on public.dufynd_ci_pr_verification_evidence to service_role;
insert into public.dufynd_handler_contracts(handler_id,handler_version,contract,enabled)
select 'ci_pr_verifier','1',contract||jsonb_build_object(
 'handler_id','ci_pr_verifier',
 'capabilities','["github.ci.observe","github.read","supabase.execution_state","supabase.task_state"]'::jsonb,
 'required_capabilities','["github.ci.observe","github.read","supabase.execution_state","supabase.task_state"]'::jsonb,
 'allowed_scopes','["supervisor"]'::jsonb,
 'allowed_resources','["db:ci-pr-verification"]'::jsonb,
 'verification_policy','{"kind":"ci_pr_verifier","version":1}'::jsonb,
 'certification_status','acceptance_only',
 'allowed_task_ids','["ci_pr_verifier_acceptance_20261002"]'::jsonb),true
from public.dufynd_handler_contracts where handler_id='durability_probe' and handler_version='1';

create function public.dufynd_ci_pr_packet_valid(p_payload jsonb) returns boolean
language sql stable security invoker set search_path=public as $$
 select coalesce(jsonb_typeof(p_payload)='object'
 and p_payload-array['kind','steps','interval_seconds','pr_number','ci_run_id','expected_merge_sha','expected_pr_head_sha']='{}'::jsonb
 and p_payload->>'kind'='ci_pr_verifier' and p_payload->>'steps'='1' and p_payload->>'interval_seconds'='2'
 and coalesce(p_payload->>'pr_number','') ~ '^[1-9][0-9]{0,8}$' and p_payload->>'pr_number' not in ('0','1','598')
 and coalesce(p_payload->>'ci_run_id','') ~ '^[1-9][0-9]{0,19}$'
 and coalesce(p_payload->>'expected_merge_sha','') ~ '^[a-f0-9]{40}$'
 and coalesce(p_payload->>'expected_pr_head_sha','') ~ '^[a-f0-9]{40}$'
 and exists(select 1 from public.dufynd_external_observers where observer_id='github_pr:'||(p_payload->>'pr_number') and source_type='github_pr' and source_id=p_payload->>'pr_number' and enabled)
 and exists(select 1 from public.dufynd_external_observers where observer_id='github_ci:'||(p_payload->>'ci_run_id') and source_type='github_ci' and source_id=p_payload->>'ci_run_id' and enabled),false);
$$;

create or replace function public.normalize_dufynd_observation(p_type text,p_id text,p_raw jsonb,p_config jsonb default '{}')
returns jsonb language plpgsql immutable security invoker set search_path=public as $$
declare payload jsonb; state text; event text; x jsonb; m jsonb; result jsonb:='[]'; headers jsonb; bounce boolean;
begin
 if jsonb_typeof(p_raw) is null or length(p_raw::text)>1000000 then raise exception 'bounded response exceeded'; end if;
 if p_type='github_branch' then
  if p_raw->>'name' is distinct from p_id or coalesce(p_raw->'commit'->>'sha','') !~ '^[a-f0-9]{40}$' then raise exception 'branch identity mismatch'; end if;
  payload:=jsonb_build_object('sha',p_raw->'commit'->>'sha'); event:='github.branch.head_moved';
 elsif p_type='github_pr' then
  if p_raw->>'number' is distinct from p_id or p_raw->'base'->>'ref' is distinct from 'scentai-mvp' or coalesce(p_raw->'head'->>'sha','') !~ '^[a-f0-9]{40}$' or coalesce(p_raw->'base'->>'sha','') !~ '^[a-f0-9]{40}$' then raise exception 'PR identity mismatch'; end if;
  state:=case when p_raw->>'merged'='true' then 'merged' when p_raw->>'state'='closed' then 'closed' else 'open' end;
  payload:=jsonb_build_object('state',state,'sha',p_raw->'head'->>'sha','base_sha',p_raw->'base'->>'sha','base_ref',p_raw->'base'->>'ref','merge_commit_sha',p_raw->>'merge_commit_sha','updated_at',p_raw->>'updated_at'); event:='github.pr.'||state;
 elsif p_type in ('github_ci','github_workflow') then
  if p_raw->>'id' is distinct from p_id or p_raw->>'head_branch' is distinct from 'scentai-mvp' or coalesce(p_raw->>'head_sha','') !~ '^[a-f0-9]{40}$' then raise exception 'run identity mismatch'; end if;
  if p_type='github_ci' and p_raw->>'path' is distinct from '.github/workflows/ci.yml' then raise exception 'CI workflow mismatch'; end if;
  state:=case when p_raw->>'status'='completed' then case when p_raw->>'conclusion'='success' then 'success' else 'failure' end
   when p_raw->>'status'='in_progress' then 'in_progress' when p_raw->>'status' in ('queued','waiting','pending','requested') then 'queued' else null end;
  if state is null then raise exception 'unknown run state'; end if;
  payload:=jsonb_build_object('state',state,'sha',p_raw->>'head_sha','run_id',p_id,'attempt',p_raw->'run_attempt','conclusion',p_raw->>'conclusion');
  event:=case when p_type='github_ci' then 'github.ci.' else 'github.workflow.' end||state;
 elsif p_type='render' then
  if jsonb_typeof(p_raw) is distinct from 'array' or jsonb_array_length(p_raw)>20 then raise exception 'bounded deploy list required'; end if;
  for x in select value from jsonb_array_elements(p_raw) loop
   m:=coalesce(x->'deploy',x); state:=case when m->>'status'='live' then 'live'
    when m->>'status' in ('build_failed','update_failed','pre_deploy_failed','canceled') then 'failed'
    when m->>'status' in ('created','queued','build_in_progress','update_in_progress','pre_deploy_in_progress') then 'started' else null end;
   if state is not null and nullif(m->>'id','') is not null then
    result:=result||jsonb_build_array(jsonb_build_object('event_type','render.deployment.'||state,'cursor',(m->>'id')||':'||(m->>'status'),
    'payload',jsonb_build_object('state',state,'deployment_id',m->>'id','service_id',p_id,'sha',m->'commit'->>'id')));
   if state='live' and coalesce(m->'commit'->>'id','') ~ '^[a-f0-9]{40}$' then
     result:=result||jsonb_build_array(jsonb_build_object('event_type','render.service.commit','cursor',m->'commit'->>'id','payload',jsonb_build_object('service_id',p_id,'sha',m->'commit'->>'id')));
    end if;
   end if;
  end loop; return result;
 elsif p_type='gmail' then
  -- Native history response: only messageAdded from the explicitly registered thread.
  if coalesce(p_raw->>'historyId','') !~ '^[0-9]+$' then raise exception 'invalid Gmail history cursor'; end if;
  if not p_raw ? 'id' and not p_raw ? 'messages' and not p_raw ? 'history' then return '[]'; end if;
  if p_raw ? 'history' then
   if jsonb_typeof(p_raw->'history') is distinct from 'array' then raise exception 'invalid history'; end if;
   if jsonb_array_length(p_raw->'history')>100 then raise exception 'bounded Gmail history required'; end if;
   for x in select value from jsonb_array_elements(p_raw->'history') loop
    for m in select value->'message' from jsonb_array_elements(coalesce(x->'messagesAdded','[]')) loop
     if m->>'threadId'=p_id and not coalesce(m->'labelIds','[]') ? 'SENT' then
      result:=result||jsonb_build_array(jsonb_build_object('event_type','gmail.message.received','cursor',x->>'id','payload',jsonb_build_object('thread_id',p_id,'message_id',m->>'id','history_id',x->>'id')));
     end if;
    end loop;
   end loop; return result;
  end if;
  if p_raw->>'id' is distinct from p_id or jsonb_typeof(p_raw->'messages') is distinct from 'array' or jsonb_array_length(p_raw->'messages')>100 then raise exception 'known bounded Gmail thread required'; end if;
  for m in select value from jsonb_array_elements(p_raw->'messages') loop
   if coalesce(m->>'id','') !~ '^[a-f0-9]+$' or coalesce(m->>'internalDate','') !~ '^[0-9]+$' or m->>'threadId' is distinct from p_id then raise exception 'foreign message rejected'; end if;
   if coalesce(m->'labelIds','[]') ? 'SENT' or coalesce(m->'labelIds','[]') ? 'DRAFT' then continue; end if;
   headers:=coalesce(m->'payload'->'headers','[]');
   bounce:=exists(select 1 from jsonb_array_elements(headers) h where lower(h->>'name')='content-type' and lower(h->>'value') like '%delivery-status%')
    or exists(select 1 from jsonb_array_elements(headers) h where lower(h->>'name')='from' and lower(h->>'value') ~ '(mailer-daemon|postmaster)');
   result:=result||jsonb_build_array(jsonb_build_object('event_type',case when bounce then 'gmail.delivery_failure' else 'gmail.message.received' end,
    'cursor',p_raw->>'historyId','payload',jsonb_build_object('thread_id',p_id,'message_id',m->>'id','internal_date',m->>'internalDate','history_id',p_raw->>'historyId')));
  end loop; return result;
 elsif p_type='internal_dependency' then
  if p_raw->>'task_id' is distinct from p_id or p_raw->>'status' is distinct from 'done' then return '[]'; end if;
  payload:=jsonb_build_object('task_id',p_id,'state','done'); event:='internal.dependency.completed';
 else raise exception 'unknown source'; end if;
 return jsonb_build_array(jsonb_build_object('event_type',event,'cursor',coalesce(payload->>'updated_at',payload->>'sha',payload->>'state'),'payload',payload));
end $$;

create function public.read_dufynd_ci_pr_audit(p_payload jsonb) returns jsonb
language plpgsql security invoker set search_path=public as $$
declare pr public.dufynd_external_observers; ci public.dufynd_external_observers; decision text;
begin
 if not public.dufynd_ci_pr_packet_valid(p_payload) then return null; end if;
 select * into pr from public.dufynd_external_observers where observer_id='github_pr:'||(p_payload->>'pr_number');
 select * into ci from public.dufynd_external_observers where observer_id='github_ci:'||(p_payload->>'ci_run_id');
 decision:=case
  when pr.health_status<>'healthy' or ci.health_status<>'healthy' or pr.last_success_at is null or ci.last_success_at is null
   or pr.last_success_at<now()-interval '20 minutes' or ci.last_success_at<now()-interval '20 minutes'
   or pr.last_success_at>now() or ci.last_success_at>now() then 'source_unverified_or_stale'
  when pr.last_snapshot->>'state' is distinct from 'merged' or pr.last_snapshot->>'base_ref' is distinct from 'scentai-mvp' then 'pr_not_merged_to_integration'
  when pr.last_snapshot->>'sha' is distinct from p_payload->>'expected_pr_head_sha'
   or pr.last_snapshot->>'merge_commit_sha' is distinct from p_payload->>'expected_merge_sha' then 'pr_sha_mismatch'
  when ci.last_snapshot->>'run_id' is distinct from p_payload->>'ci_run_id'
   or ci.last_snapshot->>'sha' is distinct from p_payload->>'expected_merge_sha' then 'ci_sha_mismatch'
  when ci.last_snapshot->>'state' is distinct from 'success' or ci.last_snapshot->>'conclusion' is distinct from 'success' then 'ci_not_successful'
  else 'verified' end;
 return jsonb_build_object('audit_version',1,'source','registered_github_observers','decision',decision,
  'repository','tncommerce/commerce-agents','branch','scentai-mvp','checked_at',now(),
  'pr_number',p_payload->>'pr_number','ci_run_id',p_payload->>'ci_run_id',
  'expected_merge_sha',p_payload->>'expected_merge_sha','expected_pr_head_sha',p_payload->>'expected_pr_head_sha',
  'pr',jsonb_build_object('observer_id',pr.observer_id,'observed_at',pr.last_success_at,'snapshot',pr.last_snapshot),
  'ci',jsonb_build_object('observer_id',ci.observer_id,'observed_at',ci.last_success_at,'snapshot',ci.last_snapshot),
  'approvals_inferred',false,'deployment_verified',false,'business_mutations',false);
end $$;

create function public.schedule_dufynd_ci_pr_verification(p_pr_number text,p_ci_run_id text,p_merge_sha text,p_pr_head_sha text,p_acceptance boolean default false) returns jsonb
language plpgsql security invoker set search_path=public as $$
declare payload jsonb; tid text; pr text; ci text; t public.dufynd_autonomy_tasks;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 if coalesce(p_pr_number,'') !~ '^[1-9][0-9]{0,8}$' or p_pr_number in ('1','598')
 or coalesce(p_ci_run_id,'') !~ '^[1-9][0-9]{0,19}$' or coalesce(p_merge_sha,'') !~ '^[a-f0-9]{40}$'
 or coalesce(p_pr_head_sha,'') !~ '^[a-f0-9]{40}$' then return jsonb_build_object('scheduled',false,'reason','invalid_exact_target'); end if;
 payload:=jsonb_build_object('kind','ci_pr_verifier','steps',1,'interval_seconds',2,'pr_number',p_pr_number,
  'ci_run_id',p_ci_run_id,'expected_merge_sha',p_merge_sha,'expected_pr_head_sha',p_pr_head_sha);
 tid:=case when p_acceptance then 'ci_pr_verifier_acceptance_20261002'
  else 'ci-pr:'||encode(sha256(convert_to(payload::text,'UTF8')),'hex') end;
 select * into t from public.dufynd_autonomy_tasks where task_id=tid;
 if found then return jsonb_build_object('scheduled',t.durable_payload=payload,'reused',true,'task_id',tid); end if;
 if not exists(select 1 from public.dufynd_handler_contracts where handler_id='ci_pr_verifier' and handler_version='1' and enabled
  and (contract->>'certification_status'='certified' or (p_acceptance and contract->>'certification_status'='acceptance_only')))
 then return jsonb_build_object('scheduled',false,'reason','handler_not_admitted'); end if;
 pr:=public.register_dufynd_observer('github_pr',p_pr_number);
 ci:=public.register_dufynd_observer('github_ci',p_ci_run_id);
 insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,worker_state,requires_human_approval,dependencies,
  budget_class,resource_scope,durability_policy,required_capabilities,durable_payload)
 values(tid,'supervisor','Verify exact merged PR and successful integration CI','Read registered GitHub snapshots only. No approval, merge or deploy action.',
  'waiting_external','waiting_external',false,'[]','free','["db:ci-pr-verification"]','durable',
  '["github.ci.observe","github.read","supabase.execution_state","supabase.task_state"]',payload);
 perform public.bind_dufynd_external_wait(tid,pr,'["github.pr.merged"]',p_pr_head_sha);
 perform public.bind_dufynd_external_wait(tid,ci,'["github.ci.success"]',p_merge_sha);
 -- Reuse already persisted, fresh, matching source events when an observer was
 -- registered before this waiter. No fabricated event, HTTP replay or new queue.
 update public.dufynd_task_external_waits w set satisfied=true,last_event_id=ev.event_id,reevaluated_at=now()
 from public.dufynd_external_observers o,public.dufynd_jarvis_inbox ev
 where w.task_id=tid and w.observer_id=o.observer_id and o.health_status='healthy'
 and o.last_success_at between now()-interval '20 minutes' and now()
 and ev.payload->>'observer_id'=o.observer_id and ev.payload->'evidence'=o.last_snapshot
 and w.event_types ? ev.event_type and ev.payload->'evidence'->>'sha'=w.expected_sha;
 return jsonb_build_object('scheduled',true,'reused',false,'task_id',tid);
end $$;

create or replace function public.select_dufynd_handler(p_task_id text,p_scope text,p_resources jsonb,p_payload jsonb,p_policy text)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare t public.dufynd_autonomy_tasks; h public.dufynd_handler_contracts; needed jsonb;
begin
 select * into t from public.dufynd_autonomy_tasks where task_id=p_task_id;
 if not found or not public.dufynd_capability_list_valid(t.required_capabilities)
 or not public.dufynd_capability_list_valid(t.forbidden_actions)
 or t.resource_scope is distinct from p_resources or not public.dufynd_valid_resource_scope(p_resources)
 or t.domain is distinct from 'supervisor'
 or t.budget_class is distinct from 'free' or t.provider_cost_unknown or t.requires_human_approval
 or jsonb_typeof(t.dependencies) is distinct from 'array'
 or jsonb_array_length(t.dependencies)>32
 or exists(select 1 from jsonb_array_elements_text(t.dependencies) dep
 left join public.dufynd_autonomy_tasks d on d.task_id=dep where d.status is distinct from 'done')
 or t.external_review_required or t.needs_freshness_recheck
 or p_policy<>'durable' or t.durability_policy<>p_policy then return null; end if;
 if p_payload->>'kind'='purchase_destination_freshness_audit' and not coalesce(public.dufynd_purchase_packet_valid(p_payload),false) then return null; end if;
 if p_payload->>'kind'='ci_pr_verifier' and (not public.dufynd_ci_pr_packet_valid(p_payload) or t.durable_payload is distinct from p_payload) then return null; end if;
 -- Selection is stable: lexicographic handler ID/version after all policy filters.
 for h in select * from public.dufynd_handler_contracts where enabled
 and handler_id=p_payload->>'kind' order by handler_id collate "C",handler_version collate "C" loop
  if h.handler_id not in ('durability_probe','supervisor_state_audit','purchase_destination_freshness_audit','ci_pr_verifier') or h.handler_version<>'1'
  or (h.handler_id in ('supervisor_state_audit','purchase_destination_freshness_audit','ci_pr_verifier') and (coalesce(h.contract->>'certification_status','') not in ('acceptance_only','certified')
   or (h.contract->>'certification_status'='acceptance_only' and not coalesce(h.contract->'allowed_task_ids' ? p_task_id,false))))
  or h.contract->>'handler_id' is distinct from h.handler_id
  or h.contract->>'handler_version' is distinct from h.handler_version
  or not public.dufynd_capability_list_valid(h.contract->'capabilities')
  or not public.dufynd_capability_list_valid(h.contract->'required_capabilities')
  or not public.dufynd_capability_list_valid(h.contract->'forbidden_actions')
  or h.contract->>'risk_class' is distinct from 'low'
  or h.contract->>'cost_class' is distinct from 'free'
  or h.contract->>'durability_class' is distinct from p_policy
  or h.contract->'required_approval_class' is distinct from 'null'::jsonb
  or not coalesce(h.contract->'allowed_scopes' ? p_scope,false)
  or jsonb_typeof(h.contract->'allowed_resources') is distinct from 'array'
  or h.contract->'allowed_tools' is distinct from '["checkpoint_dufynd_execution","finish_dufynd_execution"]'::jsonb
  or h.contract->'verification_policy' is distinct from jsonb_build_object('kind',case when h.handler_id='durability_probe' then 'arithmetic_checkpoint' else h.handler_id end,'version',1)
  or h.contract->'supports_retry' is distinct from 'true'::jsonb
  or h.contract->'supports_parallel_execution' is distinct from 'true'::jsonb then continue; end if;
  select jsonb_agg(v order by v) into needed from (
   select distinct v from jsonb_array_elements_text(t.required_capabilities||(h.contract->'required_capabilities')) v) q;
  if not coalesce(h.contract->'capabilities' @> needed,false)
  or exists(select 1 from jsonb_array_elements_text(needed) v where t.forbidden_actions ? v or h.contract->'forbidden_actions' ? v)
  or exists(select 1 from jsonb_array_elements_text(t.forbidden_actions) v where h.contract->'allowed_tools' ? v)
  or exists(select 1 from jsonb_array_elements_text(h.contract->'capabilities') v where v in ('gmail.send','social.publish','budget.spend','main.merge','commerce.activate','shell.execute'))
  or exists(select 1 from jsonb_array_elements_text(p_resources) r where not exists(
    select 1 from jsonb_array_elements_text(h.contract->'allowed_resources') prefix
    where (h.handler_id='durability_probe' and prefix in ('db:','external:') and starts_with(r,prefix))
    or (h.handler_id='supervisor_state_audit' and r=prefix and r='db:jarvis.supervisor_v2.health')
    or (h.handler_id='purchase_destination_freshness_audit' and r=prefix and r='db:purchase-evidence:perfumetrader-rabanne-1-million-edt-100')
    or (h.handler_id='ci_pr_verifier' and r=prefix and r='db:ci-pr-verification'))) then continue; end if;
  return h.contract||jsonb_build_object('effective_capabilities',needed);
 end loop;
 return null;
end $$;

create or replace function public.certify_dufynd_execution_packet() returns trigger
language plpgsql security invoker set search_path=public as $$
declare h jsonb; t public.dufynd_autonomy_tasks; deps jsonb; denied jsonb;
begin
 if TG_OP='UPDATE' then
  if (new.task_packet,new.packet_hash,new.handler_id,new.handler_version,new.payload,new.resources,new.scope,new.task_id,new.idempotency_key,new.request_hash)
  is distinct from (old.task_packet,old.packet_hash,old.handler_id,old.handler_version,old.payload,old.resources,old.scope,old.task_id,old.idempotency_key,old.request_hash) then
   raise exception 'immutable execution packet; create an explicit new execution/version';
  end if;
  return new;
 end if;
 h:=public.select_dufynd_handler(new.task_id,new.scope,new.resources,new.payload,new.durability_policy);
 if h is null then raise exception 'uncertified capability/scope/resource contract'; end if;
 select * into t from public.dufynd_autonomy_tasks where task_id=new.task_id;
 select coalesce(jsonb_agg(jsonb_build_object('task_id',d.task_id,'status',d.status) order by d.task_id),'[]') into deps
 from public.dufynd_autonomy_tasks d where t.dependencies ? d.task_id;
 select jsonb_agg(v order by v) into denied from (select distinct v from jsonb_array_elements_text(t.forbidden_actions||(h->'forbidden_actions')) v) q;
 new.handler_id:=h->>'handler_id'; new.handler_version:=h->>'handler_version';
 new.task_packet:=jsonb_build_object(
 'packet_version',1,'task_id',new.task_id,'execution_id',new.execution_id,
 'handler_id',new.handler_id,'handler_version',new.handler_version,
 'goal',case when new.handler_id='durability_probe' then 'Verify the bounded arithmetic durability probe' when new.handler_id='purchase_destination_freshness_audit' then 'Verify exact approved merchant identity and persist evidence only; no business field mutations' when new.handler_id='ci_pr_verifier' then 'Correlate exact merged integration PR and CI SHA using fresh registered observers; no approval or deployment inference' else 'Persist a bounded read-only supervisor state audit; findings are not repairs or approvals' end,
 'explicit_scope',new.scope,'required_capabilities',h->'effective_capabilities',
 'allowed_resources',new.resources,'allowed_tools',h->'allowed_tools',
 'forbidden_actions',denied,'relevant_dependencies',deps,
 'last_checkpoint',new.last_checkpoint,
 'relevant_evidence',case when t.last_external_event_id is null then '[]'::jsonb
 else jsonb_build_array(jsonb_build_object('external_event_id',t.last_external_event_id)) end,
 'expected_outputs',jsonb_build_object('step',new.payload->'steps','sum',(new.payload->>'steps')::int*((new.payload->>'steps')::int+1)/2),
 'verification_contract',h->'verification_policy','payload',new.payload,
 'retry_recovery_context',jsonb_build_object('max_attempts',3,'resume_from','persistent execution checkpoint','packet_policy','same immutable packet'),
 'idempotency_fencing',jsonb_build_object('idempotency_key',new.idempotency_key,'initial_lease_token',new.lease_token,'current_fence_source','persistent execution lease_token'),
 'handler_contract',h-'capabilities'||jsonb_build_object('capabilities',h->'effective_capabilities','allowed_resources',new.resources,'allowed_scopes',jsonb_build_array(new.scope)));
 if octet_length(new.task_packet::text)>8192 then raise exception 'task packet exceeds 8192 bytes'; end if;
 new.packet_hash:=encode(sha256(convert_to(new.task_packet::text,'UTF8')),'hex');
 new.evidence:=new.evidence||jsonb_build_array(jsonb_build_object('event','capability_matched_packet_persisted','handler_id',new.handler_id,'handler_version',new.handler_version,'packet_version',1,'packet_hash',new.packet_hash,'at',now()));
 return new;
end $$;

create or replace function public.prepare_dufynd_execution(p_task_id text,p_idempotency_key text,p_scope text,p_resources jsonb,p_payload jsonb,p_policy text default 'durable')
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
 or coalesce(p_payload->>'kind','') not in ('durability_probe','supervisor_state_audit','purchase_destination_freshness_audit','ci_pr_verifier')
 or (p_payload->>'kind' not in ('purchase_destination_freshness_audit','ci_pr_verifier') and p_payload - array['kind','steps','interval_seconds'] <> '{}'::jsonb)
 or (p_payload->>'kind'='purchase_destination_freshness_audit' and not coalesce(public.dufynd_purchase_packet_valid(p_payload),false))
 or (p_payload->>'kind'='ci_pr_verifier' and not public.dufynd_ci_pr_packet_valid(p_payload))
 or coalesce(p_payload->>'steps','') !~ '^[0-9]{1,2}$'
 or coalesce(p_payload->>'interval_seconds','') !~ '^[0-9]{1,2}$' then
  return jsonb_build_object('allowed',false,'reason','uncertified_free_handler');
 end if;
 if (p_payload->>'steps')::int not between 1 and 30 or (p_payload->>'interval_seconds')::int not between 2 and 30 then
  return jsonb_build_object('allowed',false,'reason','invalid_probe_limits');
 end if;
 if p_payload->>'kind'='supervisor_state_audit' and (p_payload->>'steps'<>'1' or p_payload->>'interval_seconds'<>'2') then return jsonb_build_object('allowed',false,'reason','invalid_audit_limits'); end if;
 fingerprint:=encode(sha256(convert_to(jsonb_build_array(p_task_id,p_scope,p_resources,p_payload,p_policy)::text,'UTF8')),'hex');
 select * into e from public.dufynd_execution_runs where idempotency_key=p_idempotency_key;
 if found then
  if e.request_hash<>fingerprint then return jsonb_build_object('allowed',false,'reason','idempotency_conflict'); end if;
  if e.task_packet is null then return jsonb_build_object('allowed',false,'reason','legacy_execution_uncertified'); end if;
  return jsonb_build_object('allowed',true,'reused',true,'execution',to_jsonb(e));
 end if;
 if exists(select 1 from public.dufynd_execution_runs where task_id=p_task_id and status not in ('completed','failed_terminal')) then
  return jsonb_build_object('allowed',false,'reason','task_already_executing');
 end if;
 insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,requires_human_approval,dependencies,budget_class,resource_scope,durability_policy)
 values(p_task_id,'supervisor','Durable deterministic verification','Execute the exact certified free handler only.','ready',false,'[]','free',p_resources,p_policy)
 on conflict(task_id) do nothing;
 select * into t from public.dufynd_autonomy_tasks where task_id=p_task_id;
 if t.budget_class<>'free' or t.provider_cost_unknown or t.resource_scope<>p_resources or t.durability_policy<>p_policy then
  return jsonb_build_object('allowed',false,'reason','task_contract_conflict');
 end if;
 if public.select_dufynd_handler(p_task_id,p_scope,p_resources,p_payload,p_policy) is null then
  return jsonb_build_object('allowed',false,'reason','capability_scope_resource_denied');
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

create or replace function public.take_dufynd_execution(p_external_run_id text,p_worker_id text,p_execution_id uuid default null)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare e public.dufynd_execution_runs; t public.dufynd_autonomy_tasks;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 if coalesce(p_external_run_id,'') !~ '^[0-9]+$' or nullif(p_worker_id,'') is null then return null; end if;
 select * into e from public.dufynd_execution_runs where status='dispatch_pending' and worker_type='github_actions'
 and public.dufynd_execution_contract_valid(execution_id)
 and (p_execution_id is null or execution_id=p_execution_id) order by created_at limit 1 for update;
 if not found or e.lease_expires_at<=now() then return null; end if;
 if not public.dufynd_execution_contract_valid(e.execution_id) then return null; end if;
 select * into t from public.dufynd_autonomy_tasks where task_id=e.task_id for update;
 if t.lease_token is distinct from e.lease_token or t.released_at is not null or t.budget_class<>'free'
 or t.lease_expires_at<=now() or e.payload->>'kind' not in ('durability_probe','supervisor_state_audit','purchase_destination_freshness_audit','ci_pr_verifier') then return null; end if;
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

create or replace function public.checkpoint_dufynd_execution(p_execution_id uuid,p_token uuid,p_worker_id text,p_step int default null)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare e public.dufynd_execution_runs; t public.dufynd_autonomy_tasks; current_step int; destination text; audit jsonb;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 select * into e from public.dufynd_execution_runs where execution_id=p_execution_id for update;
 if not found or e.lease_token is distinct from p_token or e.worker_id is distinct from p_worker_id
 or e.status not in ('dispatched','running') or e.lease_expires_at<=now() then return null; end if;
 if not public.dufynd_execution_contract_valid(e.execution_id) then return null; end if;
 select * into t from public.dufynd_autonomy_tasks where task_id=e.task_id for update;
 if t.lease_token is distinct from p_token or t.released_at is not null or t.lease_expires_at<=now() then return null; end if;
 current_step:=(e.last_checkpoint->>'step')::int;
 if p_step is not null and p_step<>current_step and (p_step<>current_step+1 or p_step>(e.payload->>'steps')::int) then return null; end if;
 if e.last_progress_at<now()-interval '600 seconds' then return null; end if;
 if e.handler_id='purchase_destination_freshness_audit' and p_step>current_step then
  perform set_config('dufynd.execution_write',e.execution_id::text,true);
  audit:=public.poll_dufynd_purchase_verification(e.execution_id);
  if audit is null then p_step:=null; end if;
 end if;
 destination:=case when coalesce(p_step,current_step)=(e.payload->>'steps')::int then 'verifying' else 'running' end;
 if e.handler_id='supervisor_state_audit' and p_step>current_step then audit:=public.read_dufynd_supervisor_audit(); end if;
 if e.handler_id='ci_pr_verifier' and p_step>current_step then audit:=public.read_dufynd_ci_pr_audit(e.payload); if audit is null then return null; end if; end if;
 perform set_config('dufynd.execution_write',e.execution_id::text,true); perform set_config('dufynd.worker_write',p_token::text,true);
 update public.dufynd_execution_runs set status=destination,heartbeat_at=now(),lease_expires_at=now()+interval '180 seconds',
 last_progress_at=case when p_step>current_step then now() else last_progress_at end,
 last_checkpoint=case when p_step>current_step then jsonb_build_object('step',p_step,'sum',p_step*(p_step+1)/2,'verified',p_step=(payload->>'steps')::int,'verified_at',now())||case when audit is null then '{}'::jsonb else jsonb_build_object('audit',audit,'audit_hash',encode(sha256(convert_to(audit::text,'UTF8')),'hex')) end else last_checkpoint end,
 evidence=case when p_step>current_step then evidence||jsonb_build_array(jsonb_build_object('event','progress','step',p_step,'at',now(),'worker_id',p_worker_id,'attempt',attempt)) else evidence end
 where execution_id=e.execution_id returning * into e;
 update public.dufynd_autonomy_tasks set worker_state=case when destination='verifying' then 'verifying' else 'working' end,heartbeat_at=now(),last_progress_at=e.last_progress_at,lease_expires_at=e.lease_expires_at,
 expected_next_checkpoint='durable_execution:'||e.execution_id::text||':step:'||(coalesce(p_step,current_step)+1)::text where task_id=e.task_id;
 perform set_config('dufynd.worker_write','',true); perform set_config('dufynd.execution_write','',true);
 return to_jsonb(e);
end $$;

create or replace function public.finish_dufynd_execution(p_execution_id uuid,p_token uuid,p_worker_id text)
returns boolean language plpgsql security invoker set search_path=public as $$
declare e public.dufynd_execution_runs; t public.dufynd_autonomy_tasks; n int;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 select * into e from public.dufynd_execution_runs where execution_id=p_execution_id for update;
 if not found or e.lease_token is distinct from p_token or e.worker_id is distinct from p_worker_id then return false; end if;
 if e.status='completed' then return true; end if;
 if not public.dufynd_execution_contract_valid(e.execution_id) then return false; end if;
 select * into t from public.dufynd_autonomy_tasks where task_id=e.task_id for update;
 if t.lease_token is distinct from p_token or t.released_at is not null then return false; end if;
 if (e.lease_expires_at<=now() or t.lease_expires_at<=now()) and coalesce(current_setting('dufynd.execution_write',true),'')<>'supervisor' then return false; end if;
 n:=(e.payload->>'steps')::int;
 if e.status<>'verifying' or e.last_checkpoint->>'verified' is distinct from 'true'
 or (e.last_checkpoint->>'step')::int<>n or (e.last_checkpoint->>'sum')::int<>n*(n+1)/2 then return false; end if;
 if e.handler_id in ('supervisor_state_audit','purchase_destination_freshness_audit','ci_pr_verifier') and (jsonb_typeof(e.last_checkpoint->'audit') is distinct from 'object'
 or (e.handler_id='supervisor_state_audit' and e.last_checkpoint->'audit'->>'audit_version' is distinct from '1')
 or e.last_checkpoint->>'audit_hash' is distinct from encode(sha256(convert_to((e.last_checkpoint->'audit')::text,'UTF8')),'hex')) then return false; end if;
 if e.handler_id='purchase_destination_freshness_audit' then
  if e.last_checkpoint->'audit'->>'source' is distinct from 'fixed_https_merchant_pg_net'
  and e.last_checkpoint->'audit'->>'decision'<>'transport_unverified' then return false; end if;
  if e.last_checkpoint->>'audit_hash' is distinct from encode(sha256(convert_to((e.last_checkpoint->'audit')::text,'UTF8')),'hex') then return false; end if;
  insert into public.dufynd_purchase_verification_evidence(execution_id,offer_id,observed_at,decision,report,report_hash)
  values(e.execution_id,e.payload->>'offer_id',(e.last_checkpoint->'audit'->>'observed_at')::timestamptz,
   e.last_checkpoint->'audit'->>'decision',e.last_checkpoint->'audit',e.last_checkpoint->>'audit_hash') on conflict do nothing;
  update public.dufynd_purchase_verification_targets set last_result=e.last_checkpoint->'audit',
   last_verified_at=case when e.last_checkpoint->'audit'->>'decision'='safe_evidence_refresh' then greatest(last_verified_at,(e.last_checkpoint->'audit'->>'observed_at')::timestamptz) else last_verified_at end,
   retry_after=case when e.last_checkpoint->'audit'->>'decision'='transport_unverified' then now()+interval '6 hours' else null end,
   certification_due=false where offer_id=e.payload->>'offer_id';
 end if;
 if e.handler_id='ci_pr_verifier' then
  if e.last_checkpoint->'audit'->>'source' is distinct from 'registered_github_observers'
  or e.last_checkpoint->'audit'->>'expected_merge_sha' is distinct from e.payload->>'expected_merge_sha'
  or e.last_checkpoint->'audit'->>'expected_pr_head_sha' is distinct from e.payload->>'expected_pr_head_sha'
  or public.dufynd_parse_timestamp(e.last_checkpoint->'audit'->>'checked_at') is null
  or public.dufynd_parse_timestamp(e.last_checkpoint->'audit'->>'checked_at')<now()-interval '20 minutes' then return false; end if;
  insert into public.dufynd_ci_pr_verification_evidence(execution_id,report,report_hash)
  values(e.execution_id,e.last_checkpoint->'audit',e.last_checkpoint->>'audit_hash') on conflict do nothing;
 end if;
 -- Verification is the SQL-derived recipe result, never success prose or exit code.
 perform set_config('dufynd.execution_write',e.execution_id::text,true); perform set_config('dufynd.worker_write',p_token::text,true);
 update public.dufynd_autonomy_tasks set status=case when (e.handler_id='purchase_destination_freshness_audit' and e.last_checkpoint->'audit'->>'decision'<>'safe_evidence_refresh') or (e.handler_id='ci_pr_verifier' and e.last_checkpoint->'audit'->>'decision'<>'verified') then 'blocked' else 'done' end,worker_state='done',evidence='Durable execution '||e.execution_id::text||' verified checkpoint '||e.last_checkpoint::text,
 released_at=now(),lease_expires_at=now(),expected_next_checkpoint=null,blocked_reason=case when (e.handler_id='purchase_destination_freshness_audit' and e.last_checkpoint->'audit'->>'decision'<>'safe_evidence_refresh') or (e.handler_id='ci_pr_verifier' and e.last_checkpoint->'audit'->>'decision'<>'verified') then e.last_checkpoint->'audit'->>'decision' else null end where task_id=e.task_id;
 update public.dufynd_execution_runs set status='completed',completed_at=now(),lease_expires_at=now(),
 evidence=evidence||jsonb_build_array(jsonb_build_object('event','verified_completed','at',now(),'worker_id',p_worker_id,'external_run_id',external_run_id,'chat_ownership',false)) where execution_id=e.execution_id;
 perform set_config('dufynd.worker_write','',true); perform set_config('dufynd.execution_write','',true);
 return true;
end $$;

create or replace function public.reconcile_dufynd_executions()
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
  if not public.dufynd_execution_contract_valid(e.execution_id) then
   findings:=findings||jsonb_build_array(jsonb_build_object('id',e.execution_id,'reason','capability_contract_revoked_or_changed'));
   continue;
  end if;
  -- Handoff owns a bounded queue lease, never a chat lease. Keep Phase-1
  -- reconciliation from confusing queued dispatch with a silent worker.
  if e.handler_id in ('purchase_destination_freshness_audit','ci_pr_verifier') and e.status='dispatch_pending' and e.lease_expires_at>now() then
   perform set_config('dufynd.execution_write','supervisor',true); perform set_config('dufynd.worker_write','supervisor',true);
   update public.dufynd_execution_runs set status='running',worker_type='deterministic_supervisor',worker_id='supervisor_v2',started_at=coalesce(started_at,now()),heartbeat_at=now(),last_progress_at=now(),lease_expires_at=now()+interval '180 seconds',
    evidence=evidence||jsonb_build_array(jsonb_build_object('event','certified_supervisor_dispatch','at',now(),'chat_ownership',false)) where execution_id=e.execution_id returning * into e;
   update public.dufynd_autonomy_tasks set worker_owner='supervisor_v2',worker_state='working',heartbeat_at=now(),last_progress_at=now(),lease_expires_at=e.lease_expires_at where task_id=e.task_id;
  end if;
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
   if e.payload->>'kind' not in ('durability_probe','supervisor_state_audit','purchase_destination_freshness_audit','ci_pr_verifier') then continue; end if;
   perform set_config('dufynd.execution_write','supervisor',true); perform set_config('dufynd.worker_write','supervisor',true);
   update public.dufynd_execution_runs set status='running',worker_type='deterministic_supervisor',worker_id='supervisor_v2',attempt=attempt+1,
    heartbeat_at=now(),last_progress_at=now(),lease_expires_at=now()+interval '180 seconds',external_checked_at=null,
    evidence=evidence||jsonb_build_array(jsonb_build_object('event','checkpoint_resumed','at',now(),'checkpoint',last_checkpoint)) where execution_id=e.execution_id returning * into e;
   update public.dufynd_autonomy_tasks set worker_owner='supervisor_v2',worker_state='working',heartbeat_at=now(),last_progress_at=now(),lease_expires_at=e.lease_expires_at where task_id=e.task_id;
  end if;
  if e.worker_type='deterministic_supervisor' and e.status='running' then
   step:=(e.last_checkpoint->>'step')::int+1;
   perform public.checkpoint_dufynd_execution(e.execution_id,e.lease_token,e.worker_id,step);
   if step=(e.payload->>'steps')::int then perform set_config('dufynd.execution_write','supervisor',true); perform public.finish_dufynd_execution(e.execution_id,e.lease_token,e.worker_id); end if;
  end if;
 end loop;
 perform set_config('dufynd.worker_write','',true); perform set_config('dufynd.execution_write','',true);
 return jsonb_build_object('checked_at',now(),'findings',findings);
end $$;

create function public.certify_dufynd_ci_pr_verifier(p_execution_id uuid) returns boolean
language plpgsql security invoker set search_path=public as $$
declare e public.dufynd_execution_runs; t public.dufynd_autonomy_tasks; r public.dufynd_ci_pr_verification_evidence;
begin
 select * into e from public.dufynd_execution_runs where execution_id=p_execution_id;
 select * into t from public.dufynd_autonomy_tasks where task_id=e.task_id;
 select * into r from public.dufynd_ci_pr_verification_evidence where execution_id=e.execution_id;
 if e.task_id is distinct from 'ci_pr_verifier_acceptance_20261002' or e.handler_id is distinct from 'ci_pr_verifier'
 or e.status is distinct from 'completed' or t.status is distinct from 'done' or t.budget_class is distinct from 'free'
 or t.released_at is null or r.report->>'decision' is distinct from 'verified'
 or r.report->>'source' is distinct from 'registered_github_observers'
 or r.report_hash is distinct from e.last_checkpoint->>'audit_hash'
 or r.report_hash is distinct from encode(sha256(convert_to(r.report::text,'UTF8')),'hex')
 or not public.dufynd_execution_contract_valid(e.execution_id)
 or (select count(*) from public.dufynd_task_external_waits where task_id=e.task_id and satisfied and last_event_id is not null and policy='dependency')<>2 then return false; end if;
 update public.dufynd_handler_contracts set contract=(contract-'allowed_task_ids')||jsonb_build_object('certification_status','certified','certification_execution_id',e.execution_id,'certification_report_hash',r.report_hash)
 where handler_id='ci_pr_verifier' and handler_version='1';
 return found;
end $$;

-- Project the fourth exact acceptance receipt through the existing watchdog.
-- Bounded receipt projection inside the existing watchdog; no queue or new poll.
create or replace function public.project_dufynd_acceptance_receipts() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare m public.dufynd_master_status; e public.dufynd_execution_runs; t public.dufynd_autonomy_tasks;
 verified boolean; destination text; receipt jsonb; changed int:=0;
begin
 for m in select * from public.dufynd_master_status where key in
 ('jarvis.external_observer.acceptance','jarvis.capability_packet.acceptance','jarvis.state_audit.acceptance','jarvis.purchase_freshness.acceptance','jarvis.ci_pr_verifier.acceptance') for update loop
  select * into e from public.dufynd_execution_runs where task_id=m.value->>'task_id'
   and (nullif(m.value->>'execution_id','') is null or execution_id::text=m.value->>'execution_id')
   order by created_at desc limit 1;
  if not found or coalesce(e.handler_id,e.payload->>'kind') not in ('durability_probe','supervisor_state_audit','purchase_destination_freshness_audit','ci_pr_verifier') then continue; end if;
  select * into t from public.dufynd_autonomy_tasks where task_id=e.task_id;
  verified:=e.status='completed' and e.last_checkpoint->>'verified'='true'
    and t.status='done' and t.released_at is not null and t.budget_class='free';
  destination:=case when verified then case when m.value->>'status'='live_accepted' then 'live_accepted' else 'live_execution_verified' end
    when e.status='completed' and t.status='blocked' then 'execution_review_required'
    when e.status='failed_terminal' then 'execution_failed_terminal'
    when e.status in ('retryable','stale') then 'execution_recovery_pending'
    else 'execution_in_progress' end;
  -- Full phase acceptance (CI, deploy, source-event proof) is never fabricated here.
  receipt:=jsonb_build_object('receipt_version',1,'execution_id',e.execution_id,'task_id',e.task_id,
   'execution_status',e.status,'execution_verified',coalesce(verified,false),
   'worker_type',e.worker_type,'external_run_id',e.external_run_id,
   'handler_id',coalesce(e.handler_id,e.payload->>'kind'),'handler_version',e.handler_version,
   'packet_version',e.task_packet->'packet_version','packet_hash',e.packet_hash,
   'checkpoint_step',e.last_checkpoint->'step','checkpoint_verified',e.last_checkpoint->'verified',
   'report_hash',e.last_checkpoint->'audit_hash','completed_at',e.completed_at,
   'lease_released',t.released_at is not null,
   'dispatch_count',(select count(*) from jsonb_array_elements(e.evidence) v where v->>'event' in ('external_dispatch_bound','certified_supervisor_dispatch')),
   'source','persistent_execution_ledger','ci_acceptance_inferred',false);
  if m.value->'execution_receipt' is distinct from receipt or m.value->>'status' is distinct from destination then
   update public.dufynd_master_status set value=value||jsonb_build_object('status',destination,'execution_receipt',receipt),last_verified_at=now() where key=m.key;
   changed:=changed+1;
  end if;
 end loop;
 return jsonb_build_object('projected',changed);
end $$;

do $$ declare f record; begin
 for f in select oid::regprocedure signature from pg_proc where pronamespace='public'::regnamespace and proname in
 ('dufynd_ci_pr_packet_valid','read_dufynd_ci_pr_audit','schedule_dufynd_ci_pr_verification','certify_dufynd_ci_pr_verifier') loop
 execute 'revoke all on function '||f.signature||' from public,anon,authenticated';
 execute 'grant execute on function '||f.signature||' to service_role';
 end loop;
end $$;
