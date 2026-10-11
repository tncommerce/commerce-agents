-- PREPARED ONLY. Production migration AND activation require separate Owner GO.
-- Reuse existing decisions, tasks, leases, master-status receipts. No cron/queue.
create function public.dufynd_content7_activation_allowed_v1(p_round text)
returns boolean language plpgsql security invoker set search_path=public as $$
declare receipt jsonb; ctx jsonb; d public.dufynd_human_decisions;
begin
 select value into receipt from public.dufynd_master_status
 where key='content.seven_workers.activation.'||p_round for share;
 if receipt is null or receipt->'active' is distinct from 'true'::jsonb then return false; end if;
 select * into d from public.dufynd_human_decisions
 where decision_id=receipt->>'decision_id' for share;
 select value into ctx from public.dufynd_master_status
 where key='content.seven_workers.runtime.source.'||p_round for share;
 return coalesce(d.status='approved' and d.action_type='content7_atomic_activation'
  and d.context=jsonb_build_object('round_id',p_round,'plan_sha256',receipt->>'plan_sha256',
    'source_sha256',receipt->>'source_sha256')
  and public.dufynd_content7_sha_v1(ctx)=receipt->>'source_sha256',false);
end $$;

create function public.activate_dufynd_content7_v1(p_decision_id text,p_plan jsonb)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare
 ctx jsonb:=p_plan->'context'; rid text:=p_plan#>>'{context,round}';
 sh text:=public.dufynd_content7_sha_v1(ctx); ph text:=public.dufynd_content7_sha_v1(p_plan);
 d public.dufynd_human_decisions; receipt jsonb; old jsonb; idea jsonb; ref record;
 r text; deps jsonb; fp text; source_key text; seen text[]:='{}';
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 if rid is null or rid !~ '^dufynd_editorial_[a-z0-9_]{6,100}$'
 or p_plan is distinct from jsonb_build_object('schema_version',1,'context',ctx,
  'source_sha256',sh,'scope','content7_validation_handoff_only','spend_cap_eur',0,
  'max_tasks',7,'max_candidates',3,'provider_execution',false,'publication_allowed',false)
 or ctx#>>'{pilot,round_id}' is distinct from rid
 or ctx#>'{pilot,input_version}' is distinct from '2'::jsonb
 or ctx#>>'{pilot,provenance,producer}' is null
 or ctx#>>'{pilot,provenance,producer}' not in ('work_editorial','human_editorial')
 or ctx#>'{pilot,provenance,cost_eur}' is distinct from '0'::jsonb
 or ctx#>'{pilot,provenance,provider_requests}' is distinct from '0'::jsonb
 or ctx#>'{pilot,provenance,autonomous_generation}' is distinct from 'false'::jsonb
 or octet_length(p_plan::text)>500000 then raise exception 'invalid_activation_plan'; end if;
 select * into d from public.dufynd_human_decisions where decision_id=p_decision_id for share;
 if d.status is distinct from 'approved' or d.action_type is distinct from 'content7_atomic_activation'
 or d.context is distinct from jsonb_build_object('round_id',rid,'plan_sha256',ph,'source_sha256',sh)
 then raise exception 'exact_owner_activation_go_required'; end if;
 select value into old from public.dufynd_master_status where key='content.seven_workers.activation.'||rid for update;
 if old is not null then
  if old->>'plan_sha256' is distinct from ph then raise exception 'immutable_activation_conflict'; end if;
  if old->'active'='true'::jsonb then
   if not public.dufynd_content7_activation_allowed_v1(rid) then raise exception 'activation_revoked'; end if;
   return old;
  end if;
  raise exception 'paused_round_requires_operator_review';
 end if;
 if ctx#>'{existing,snapshot_verified}' is distinct from 'true'::jsonb
 or ctx#>>'{existing,observed_at}' is null
 or (ctx#>>'{existing,observed_at}')::timestamptz < clock_timestamp()-interval '24 hours'
 or (ctx#>>'{existing,observed_at}')::timestamptz > clock_timestamp()
 or jsonb_typeof(ctx#>'{existing,frozen_refs}') is distinct from 'object'
 or ctx#>'{existing,frozen_refs}'='{}'::jsonb then raise exception 'fresh_freeze_snapshot_required'; end if;
 for ref in select key,value from jsonb_each(ctx#>'{existing,frozen_refs}') loop
  if not exists(select 1 from public.dufynd_master_status where key=ref.key
    and public.dufynd_content7_sha_v1(value)=ref.value->>'record_sha256')
  then raise exception 'live_freeze_snapshot_changed'; end if;
 end loop;
 if jsonb_typeof(ctx#>'{pilot,W2,ideas}') is distinct from 'array'
 or jsonb_array_length(ctx#>'{pilot,W2,ideas}')<>10 then raise exception 'ten_ideas_required'; end if;
 for idea in select value from jsonb_array_elements(ctx#>'{pilot,W2,ideas}') loop
  if coalesce(btrim(idea->>'title'),'')='' or coalesce(btrim(idea->>'hook'),'')=''
  or coalesce(btrim(idea->>'concept'),'')='' then raise exception 'incomplete_idea'; end if;
  -- Exclude mutable IDs/round/date: recycling the same idea gets the same key.
  fp:=encode(sha256(convert_to(lower(regexp_replace(btrim(idea->>'title'),'\s+',' ','g')),'UTF8')),'hex');
  if fp=any(seen) or exists(select 1 from public.dufynd_master_status where key='content.seven_workers.idea.'||fp)
  or exists(select 1 from public.dufynd_content_ideas where lower(btrim(title))=lower(btrim(idea->>'title')))
  then raise exception 'existing_content_duplicate'; end if;
  seen:=array_append(seen,fp);
 end loop;
 -- All gates above pass before the first mutation; any later error rolls back.
 foreach r in array array['W1','W3','W4','W5','W6','W2','W7'] loop
  if jsonb_typeof(ctx->'pilot'->r) is distinct from 'object' then raise exception 'role_input_missing'; end if;
  update public.dufynd_handler_contracts set enabled=true,
    contract=contract||'{"certification_status":"certified"}'::jsonb
   where handler_id='seven_content_'||lower(r)||'_v1' and handler_version='1'
    and contract->>'cost_class'='free' and contract->'new_inference_allowed'='false'::jsonb
    and contract->'publication_allowed'='false'::jsonb;
  if not found then raise exception 'free_handler_contract_missing'; end if;
 end loop;
 insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
 values('content.seven_workers.runtime.source.'||rid,'content',ctx,80,clock_timestamp());
 source_key:=coalesce(ctx#>>'{pilot,source_key}','content.seven_worker_editorial_pilot_20261011_v1');
 foreach r in array array['W1','W3','W4','W5','W6','W2','W7'] loop
  select coalesce(jsonb_agg('content7:'||rid||':'||value),'[]') into deps
   from jsonb_array_elements_text(public.dufynd_content7_dependencies_v1(r));
  insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,worker_state,
    priority,requires_human_approval,approval_action_type,dependencies,owner,resource_scope,
    budget_class,provider_cost_unknown,durability_policy,external_review_required,needs_freshness_recheck,
    required_capabilities,forbidden_actions,durable_payload)
  values('content7:'||rid||':'||r,'content','DUFYND '||r,'Validate pinned editorial input; no media or posts',
    'planned','queued',82,false,'auto_allowed',deps,'jarvis',jsonb_build_array('db:dufynd.content7.'||rid||'.'||r),
    'free',false,'durable',false,false,'["content.read","supabase.task_state"]',
    '["budget.spend","commerce.activate","gmail.send","main.merge","shell.execute","social.publish"]',
    jsonb_build_object('kind','seven_content_role_v1','version',1,'role',r,'round_id',rid,
      'source_key',source_key,'source_sha256',sh,'context_key','content.seven_workers.runtime.source.'||rid,
      'handler_id','seven_content_'||lower(r)||'_v1','provider_execution',false));
 end loop;
 foreach fp in array seen loop
  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('content.seven_workers.idea.'||fp,'content',jsonb_build_object('round_id',rid,'plan_sha256',ph),80,clock_timestamp());
 end loop;
 receipt:=jsonb_build_object('round_id',rid,'plan_sha256',ph,'source_sha256',sh,'decision_id',p_decision_id,
  'active',true,'cost_eur',0,'provider_execution',false,'publication_allowed',false,'activated_at',clock_timestamp());
 insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
 values('content.seven_workers.activation.'||rid,'content',receipt,80,clock_timestamp());
 perform public.reconcile_dufynd_supervisor_v2();
 return receipt;
end $$;

-- Stopping is fail-closed and reversible through explicit operator review.
-- Does not delete receipts, modify finals or confer permission to resume.
create function public.pause_dufynd_content7_v1(p_round text,p_plan_sha256 text)
returns boolean language plpgsql security invoker set search_path=public as $$
declare matched boolean;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 update public.dufynd_master_status set value=value||'{"active":false}'::jsonb,last_verified_at=clock_timestamp()
 where key='content.seven_workers.activation.'||p_round and value->>'plan_sha256'=p_plan_sha256;
 matched:=found;
 if matched then
  update public.dufynd_autonomy_tasks set status='blocked',worker_state='blocked',blocked_reason='activation_paused'
  where durable_payload->>'round_id'=p_round and durable_payload->>'kind'='seven_content_role_v1'
    and status in ('planned','ready')
    and (lease_token is null or released_at is not null);
 end if;
 return matched;
end $$;
revoke all on function public.dufynd_content7_activation_allowed_v1(text),
 public.activate_dufynd_content7_v1(text,jsonb),public.pause_dufynd_content7_v1(text,text) from public,anon,authenticated;
grant execute on function public.dufynd_content7_activation_allowed_v1(text),
 public.activate_dufynd_content7_v1(text,jsonb),public.pause_dufynd_content7_v1(text,text) to service_role,postgres;
