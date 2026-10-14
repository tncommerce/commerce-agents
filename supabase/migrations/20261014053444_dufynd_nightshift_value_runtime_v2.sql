-- DEVELOPMENT ONLY. Existing Jarvis tables/leases/decisions, no cron writes.
-- Reuse PR775's exact canonical helpers; install only those helpers if absent.
-- Does NOT require activating/installing the seven editorial SQL contracts.
do $install$ begin
 if to_regprocedure('public.dufynd_content7_canonical_v1(jsonb)') is null then
  execute $ddl$
create function public.dufynd_content7_canonical_v1(v jsonb) returns text
language plpgsql immutable security invoker set search_path=public as $$
declare result text;
begin
 case jsonb_typeof(v)
 when 'object' then
  select '{'||coalesce(string_agg(to_jsonb(key)::text||':'||public.dufynd_content7_canonical_v1(value),',' order by key collate "C"),'')||'}'
  into result from jsonb_each(v);
 when 'array' then
  select '['||coalesce(string_agg(public.dufynd_content7_canonical_v1(value),',' order by n),'')||']'
  into result from jsonb_array_elements(v) with ordinality a(value,n);
 else result:=v::text;
 end case;
 return result;
end $$;
  $ddl$;
 end if;
 if to_regprocedure('public.dufynd_content7_sha_v1(jsonb)') is null then
  execute $ddl$
create function public.dufynd_content7_sha_v1(v jsonb) returns text
language sql immutable security invoker set search_path=public as $$
 select encode(sha256(convert_to(public.dufynd_content7_canonical_v1(v),'UTF8')),'hex');
$$;
  $ddl$;
 end if;
end $install$;
revoke all on function public.dufynd_content7_canonical_v1(jsonb),public.dufynd_content7_sha_v1(jsonb) from public,anon,authenticated;
grant execute on function public.dufynd_content7_canonical_v1(jsonb),public.dufynd_content7_sha_v1(jsonb) to service_role,postgres;

create function public.dufynd_value_v2_open(r jsonb) returns boolean
language plpgsql security invoker set search_path=public as $$
declare d public.dufynd_human_decisions; m jsonb:=r->'manifest';
begin
 select * into d from public.dufynd_human_decisions where decision_id=r->>'decision_id' for share;
 return coalesce(r->'active'='true'::jsonb and d.status='approved'
  and d.action_type='nightshift_value_v2'
  and d.context=jsonb_build_object('run_id',m->>'run_id','manifest_sha256',public.dufynd_content7_sha_v1(m))
  and clock_timestamp()>=(m->>'starts_at')::timestamptz
  and clock_timestamp()<(m->>'ends_at')::timestamptz,false);
exception when invalid_datetime_format or datetime_field_overflow then return false;
end $$;

create function public.dufynd_value_v2_guard() returns trigger
language plpgsql security invoker set search_path=public as $$
begin
 if tg_table_name='dufynd_master_status' then
  if old.key like 'jarvis.value_v2.result.%' then raise exception 'immutable_value_receipt'; end if;
  if old.key like 'jarvis.value_v2.run.%' then
   if tg_op='DELETE' or (new.value->'manifest',new.value->'decision_id',new.value->'task_ids')
    is distinct from (old.value->'manifest',old.value->'decision_id',old.value->'task_ids')
   then raise exception 'immutable_value_manifest'; end if;
   if old.value->'active'='false'::jsonb and new.value->'active'='true'::jsonb
   then raise exception 'stopped_value_run_cannot_reopen'; end if;
  end if;
 elsif old.durable_payload->>'kind'='nightshift_value_v2' then
  if tg_op='DELETE' then raise exception 'value_task_preserved'; end if;
  if (new.task_id,new.durable_payload,new.domain,new.budget_class,new.provider_cost_unknown,
      new.requires_human_approval,new.approval_action_type,new.dependencies,new.resource_scope,
      new.required_capabilities,new.forbidden_actions,new.durability_policy,
      new.external_review_required,new.needs_freshness_recheck)
   is distinct from
     (old.task_id,old.durable_payload,old.domain,old.budget_class,old.provider_cost_unknown,
      old.requires_human_approval,old.approval_action_type,old.dependencies,old.resource_scope,
      old.required_capabilities,old.forbidden_actions,old.durability_policy,
      old.external_review_required,old.needs_freshness_recheck)
  then raise exception 'immutable_value_task'; end if;
  if new.lease_token is distinct from old.lease_token
   and current_setting('dufynd.value_write',true) is distinct from 'claim'
  then raise exception 'value_claim_rpc_required'; end if;
  if new.worker_state='done' and old.worker_state<>'done'
   and current_setting('dufynd.value_write',true) is distinct from 'commit'
  then raise exception 'atomic_value_receipt_required'; end if;
 end if;
 if tg_op='DELETE' then return old; end if;
 return new;
end $$;
create trigger aa_dufynd_value_v2_task_guard before update or delete on public.dufynd_autonomy_tasks
for each row execute function public.dufynd_value_v2_guard();
create trigger aa_dufynd_value_v2_receipt_guard before update or delete on public.dufynd_master_status
for each row execute function public.dufynd_value_v2_guard();

insert into public.dufynd_handler_contracts(handler_id,handler_version,contract,enabled)
select h,'2',jsonb_build_object('handler_id',h,'handler_version','2','cost_class','free',
 'provider_execution',false,'publication_allowed',false,'runtime','python3.12-isolated',
 'max_seconds',10),false from unnest(array['first_money_action','editorial_handoff']) h;

create function public.arm_dufynd_value_v2(p_decision text,p_manifest jsonb) returns jsonb
language plpgsql security invoker set search_path=public as $$
declare m jsonb:=p_manifest; rid text:=m->>'run_id'; d public.dufynd_human_decisions;
 r jsonb; ids jsonb:='[]'; item jsonb; tid text; sh text; name text; names text[];
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 if rid is null or rid !~ '^dufynd_value_[a-z0-9_]{6,100}$'
 or m->>'code_sha' is null or m->>'code_sha' !~ '^[a-f0-9]{40}$'
 or m is distinct from jsonb_build_object('version',2,'run_id',rid,'code_sha',m->>'code_sha',
   'starts_at',m->>'starts_at','ends_at',m->>'ends_at','sources',m->'sources','pins',m->'pins',
   'max_tasks',2,'max_attempts',3,'max_total_attempts',6,'cost_eur',0,'provider_calls',0)
 or octet_length(m::text)>250000 or jsonb_typeof(m->'sources') is distinct from 'object'
 or jsonb_typeof(m->'pins') is distinct from 'object'
 or (select count(*) from jsonb_object_keys(m->'sources'))<>3
 or (select count(*) from jsonb_object_keys(m->'pins'))<>3
 or not coalesce((m->>'ends_at')::timestamptz>(m->>'starts_at')::timestamptz
   and (m->>'ends_at')::timestamptz<=(m->>'starts_at')::timestamptz+interval '45 minutes'
   and (m->>'ends_at')::timestamptz>clock_timestamp(),false)
 then raise exception 'invalid_bounded_value_manifest'; end if;
 foreach name in array array['measurement','editorial','inventory'] loop
  if public.dufynd_content7_sha_v1(m->'sources'->name) is distinct from m->'pins'->>name
   or jsonb_typeof(m->'sources'->name->'value') is distinct from 'object'
  then raise exception 'source_binding_invalid'; end if;
 end loop;
 select * into d from public.dufynd_human_decisions where decision_id=p_decision for share;
 if d.status is distinct from 'approved' or d.action_type is distinct from 'nightshift_value_v2'
 or d.context is distinct from jsonb_build_object('run_id',rid,'manifest_sha256',public.dufynd_content7_sha_v1(m))
 then raise exception 'exact_owner_value_go_required'; end if;
 select value into r from public.dufynd_master_status where key='jarvis.value_v2.run.'||rid for update;
 if r is not null then
  if r->'manifest' is distinct from m or r->>'decision_id' is distinct from p_decision
  then raise exception 'immutable_value_manifest'; end if;
  return r; -- Exact replay never reopens a stopped run.
 end if;
 foreach name in array array['first_money_action','editorial_handoff'] loop
  names:=case name when 'first_money_action' then array['measurement'] else array['editorial','inventory'] end;
  select jsonb_object_agg(n,jsonb_build_object('key',m->'sources'->n->>'key',
   'value_sha256',public.dufynd_content7_sha_v1(m->'sources'->n->'value'))) into item from unnest(names) n;
  sh:=public.dufynd_content7_sha_v1(jsonb_build_object('handler',name||'/2','sources',item,'version','nightshift-value/2'));
  tid:='nightshift:value:v2:'||sh;
  -- Stable identity excludes run/time of acquisition. Never reinsert old work.
  if exists(select 1 from public.dufynd_autonomy_tasks where task_id=tid)
  then raise exception 'duplicate_value_task'; end if;
  ids:=ids||to_jsonb(tid);
  update public.dufynd_handler_contracts set enabled=true where handler_id=name and handler_version='2'
   and contract=jsonb_build_object('handler_id',name,'handler_version','2','cost_class','free',
    'provider_execution',false,'publication_allowed',false,'runtime','python3.12-isolated','max_seconds',10);
  if not found then raise exception 'value_contract_drift'; end if;
  insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,worker_state,
   priority,requires_human_approval,approval_action_type,dependencies,owner,resource_scope,
   budget_class,provider_cost_unknown,durability_policy,external_review_required,needs_freshness_recheck,
   required_capabilities,forbidden_actions,durable_payload)
  values(tid,'research','Private V2 '||name,'Run only the pinned deterministic handler; never publish',
   'ready','ready',80,false,'auto_allowed','[]','jarvis',jsonb_build_array('db:dufynd.value_v2.'||sh),
   'free',false,'durable',false,false,'["supabase.task_state"]',
   '["budget.spend","social.publish","gmail.send","main.merge","commerce.activate","shell.execute"]',
   jsonb_build_object('kind','nightshift_value_v2','version',2,'run_id',rid,'handler',name||'/2',
    'manifest_sha256',public.dufynd_content7_sha_v1(m),'provider_execution',false));
 end loop;
 r:=jsonb_build_object('manifest',m,'decision_id',p_decision,'task_ids',ids,'active',true,
  'attempts','{}'::jsonb,'state','armed','cost_eur',0,'provider_calls',0);
 insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
 values('jarvis.value_v2.run.'||rid,'jarvis',r,90,clock_timestamp());
 return r;
end $$;

create function public.stop_dufynd_value_v2(p_run text,p_reason text) returns jsonb
language plpgsql security invoker set search_path=public as $$
declare r jsonb;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 if p_reason not in ('expired','owner_stop','completed','runner_failure') then raise exception 'invalid_stop_reason'; end if;
 select value into r from public.dufynd_master_status where key='jarvis.value_v2.run.'||p_run for update;
 if r is null or r->'active'='false'::jsonb then return r; end if;
 perform set_config('dufynd.worker_write','supervisor',true);
 update public.dufynd_autonomy_tasks set status='blocked',worker_state='blocked',
  released_at=clock_timestamp(),lease_expires_at=clock_timestamp(),blocked_reason='value_'||p_reason
 where task_id in (select jsonb_array_elements_text(r->'task_ids')) and status<>'done';
 perform set_config('dufynd.worker_write','',true);
 r:=r||jsonb_build_object('active',false,'state',p_reason,'stopped_at',clock_timestamp());
 update public.dufynd_master_status set value=r,last_verified_at=clock_timestamp()
 where key='jarvis.value_v2.run.'||p_run;
 return r;
end $$;

create function public.claim_dufynd_value_v2(p_run text,p_code_sha text,p_token uuid) returns jsonb
language plpgsql security invoker set search_path=public as $$
declare r jsonb; m jsonb; tid text; t public.dufynd_autonomy_tasks; claimed jsonb; total integer;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 select value into r from public.dufynd_master_status where key='jarvis.value_v2.run.'||p_run for update;
 m:=r->'manifest';
 if r is null or m->>'code_sha' is distinct from p_code_sha or p_token is null then return null; end if;
 if clock_timestamp()>=(m->>'ends_at')::timestamptz then
  perform public.stop_dufynd_value_v2(p_run,'expired'); return null; end if;
 if not public.dufynd_value_v2_open(r) then return null; end if;
 select coalesce(sum(value::integer),0) into total from jsonb_each_text(r->'attempts');
 if total>=6 then return null; end if;
 for tid in select jsonb_array_elements_text(r->'task_ids') loop
  select * into t from public.dufynd_autonomy_tasks where task_id=tid for update;
  if coalesce((r->'attempts'->>tid)::integer,0)>=3 or t.status in ('done','blocked','waiting_human_input') then continue; end if;
  if t.durable_payload is distinct from jsonb_build_object('kind','nightshift_value_v2','version',2,
   'run_id',p_run,'handler',t.durable_payload->>'handler','manifest_sha256',public.dufynd_content7_sha_v1(m),'provider_execution',false)
   or t.durable_payload->>'handler' not in ('first_money_action/2','editorial_handoff/2')
   or t.budget_class is distinct from 'free' or t.provider_cost_unknown is distinct from false
   or t.requires_human_approval is distinct from false or t.dependencies is distinct from '[]'::jsonb
  then raise exception 'value_task_contract_drift'; end if;
  if not exists(select 1 from public.dufynd_handler_contracts where handler_id=split_part(t.durable_payload->>'handler','/',1)
    and handler_version='2' and enabled and contract=jsonb_build_object('handler_id',split_part(t.durable_payload->>'handler','/',1),
     'handler_version','2','cost_class','free','provider_execution',false,'publication_allowed',false,
     'runtime','python3.12-isolated','max_seconds',10)) then continue; end if;
  perform set_config('dufynd.value_write','claim',true);
  claimed:=public.claim_dufynd_worker_v2(tid,'nightshift_value_v2:'||p_code_sha,p_token);
  perform set_config('dufynd.value_write','',true);
  if claimed is null then continue; end if;
  r:=jsonb_set(r,array['attempts',tid],to_jsonb(coalesce((r->'attempts'->>tid)::integer,0)+1));
  update public.dufynd_master_status set value=r,last_verified_at=clock_timestamp() where key='jarvis.value_v2.run.'||p_run;
  return jsonb_build_object('task',claimed,'manifest',m,'token',p_token);
 end loop;
 return null;
end $$;

create function public.commit_dufynd_value_v2(p_run text,p_task text,p_token uuid,p_receipt jsonb) returns boolean
language plpgsql security invoker set search_path=public as $$
declare r jsonb; t public.dufynd_autonomy_tasks; saved jsonb; result jsonb:=p_receipt->'result'; k text; field text;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 select value into r from public.dufynd_master_status where key='jarvis.value_v2.run.'||p_run for update;
 select * into t from public.dufynd_autonomy_tasks where task_id=p_task for update;
 if not coalesce(r->'task_ids' ? p_task,false) or p_token is null or t.lease_token is distinct from p_token
 or t.worker_owner is distinct from 'nightshift_value_v2:'||(r#>>'{manifest,code_sha}') then return false; end if;
 k:='jarvis.value_v2.result.'||p_task;
 select value into saved from public.dufynd_master_status where key=k for update;
 if saved is not null then
  if saved is distinct from p_receipt then raise exception 'immutable_value_result_conflict'; end if;
  return t.status in ('done','blocked'); -- lost response replay, including after deadline/stop
 end if;
 if not public.dufynd_value_v2_open(r) or t.status is distinct from 'in_progress'
 or t.worker_state not in ('claimed','working','verifying') or t.released_at is not null
 or t.lease_expires_at is null or t.lease_expires_at<=clock_timestamp() then return false; end if;
 if not exists(select 1 from public.dufynd_handler_contracts where handler_id=split_part(t.durable_payload->>'handler','/',1)
  and handler_version='2' and enabled and contract=jsonb_build_object('handler_id',split_part(t.durable_payload->>'handler','/',1),
   'handler_version','2','cost_class','free','provider_execution',false,'publication_allowed',false,
   'runtime','python3.12-isolated','max_seconds',10)) then return false; end if;
 if p_receipt is distinct from jsonb_build_object('version',2,'task_id',p_task,'handler',t.durable_payload->>'handler',
  'manifest_sha256',public.dufynd_content7_sha_v1(r->'manifest'),'result',result,
  'result_sha256',public.dufynd_content7_sha_v1(result)) or octet_length(p_receipt::text)>250000
 or jsonb_typeof(result) is distinct from 'object' then raise exception 'invalid_value_receipt'; end if;
 foreach field in array array['cost_eur','provider_calls'] loop
  if result->field is distinct from '0'::jsonb then raise exception 'nonzero_value_cost'; end if;
 end loop;
 foreach field in array array['publishing_allowed','creative_approval','production_activation'] loop
  if result->field is distinct from 'false'::jsonb then raise exception 'unsafe_value_output'; end if;
 end loop;
 if result->>'state' is null or result->>'state' not in ('OWNER_HOLD',
   case t.durable_payload->>'handler' when 'first_money_action/2' then 'INTERNAL_ACTION_RECEIPT' else 'INTERNAL_EDITORIAL_HANDOFF' end)
 then raise exception 'invalid_value_state'; end if;
 if t.durable_payload->>'handler'='editorial_handoff/2' and result->>'state'<>'OWNER_HOLD'
 and (result->'required_visual_score' is distinct from '9.5'::jsonb
   or result->'visual_score' is distinct from 'null'::jsonb or result->'ready_for_owner_visual_review' is distinct from 'false'::jsonb
   or result->'scheduled' is distinct from 'false'::jsonb)
 then raise exception 'visual_gate_required'; end if;
 insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
 values(k,'jarvis',p_receipt,90,clock_timestamp());
 perform set_config('dufynd.value_write','commit',true);
 if result->>'state'='OWNER_HOLD' then
  if not public.update_dufynd_worker_v2(p_task,p_token,'blocked',k,'verification_pending') then raise exception 'lease_lost'; end if;
 else
  if not public.update_dufynd_worker_v2(p_task,p_token,'verifying',k,null)
   or not public.update_dufynd_worker_v2(p_task,p_token,'done',k,null) then raise exception 'lease_lost'; end if;
 end if;
 if clock_timestamp()>=(r#>>'{manifest,ends_at}')::timestamptz
  or clock_timestamp()>=t.lease_expires_at then raise exception 'deadline_or_lease_during_commit'; end if;
 perform set_config('dufynd.value_write','',true);
 return true;
end $$;

-- All functions are invoker-only server APIs; no public/browser grants.
do $$ declare f record; begin
 for f in select p.oid::regprocedure as signature from pg_proc p join pg_namespace n on n.oid=p.pronamespace
 where n.nspname='public' and p.proname in ('dufynd_value_v2_open','dufynd_value_v2_guard',
 'arm_dufynd_value_v2','stop_dufynd_value_v2','claim_dufynd_value_v2','commit_dufynd_value_v2') loop
  execute format('revoke all on function %s from public,anon,authenticated',f.signature);
  execute format('grant execute on function %s to service_role,postgres',f.signature);
 end loop;
end $$;
