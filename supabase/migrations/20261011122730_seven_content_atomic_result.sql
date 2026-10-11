-- DEV REVIEW ONLY. No production application/activation without separate Owner GO.
-- Existing tables/control plane only. No cron, new queue, model or public grants.

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
create function public.dufynd_content7_sha_v1(v jsonb) returns text
language sql immutable security invoker set search_path=public as $$
 select encode(sha256(convert_to(public.dufynd_content7_canonical_v1(v),'UTF8')),'hex');
$$;
create function public.dufynd_content7_dependencies_v1(r text) returns jsonb
language sql immutable security invoker set search_path=public as $$
 select case r when 'W1' then '[]'::jsonb
 when 'W3' then '["W1"]'::jsonb when 'W4' then '["W1"]'::jsonb
 when 'W5' then '["W1","W3"]'::jsonb when 'W6' then '["W1","W3","W5"]'::jsonb
 when 'W2' then '["W1","W3","W4","W5","W6"]'::jsonb
 when 'W7' then '["W1","W2","W3","W4","W5","W6"]'::jsonb end;
$$;

-- Seven individually named contracts remain DISABLED after migration. Neither
-- applying this file nor setting the client's environment flag activates tasks.
insert into public.dufynd_handler_contracts(handler_id,handler_version,contract,enabled)
select 'seven_content_'||lower(r)||'_v1','1',jsonb_build_object(
 'handler_id','seven_content_'||lower(r)||'_v1','role',r,'version',1,
 'cost_class','free','certification_status','pending_activation_review',
 'required_capabilities','["content.read","supabase.task_state"]'::jsonb,
 'forbidden_actions','["budget.spend","commerce.activate","gmail.send","main.merge","shell.execute","social.publish"]'::jsonb,
 'allowed_tools','["claim_dufynd_worker_v2","update_dufynd_worker_v2","commit_dufynd_content7_result_v1"]'::jsonb,
 'resource_template','db:dufynd.content7.{round}.{role}',
 'dependencies',public.dufynd_content7_dependencies_v1(r),'new_inference_allowed',false,
 'supports_retry',true,'publication_allowed',false),false
from unnest(array['W1','W2','W3','W4','W5','W6','W7']) r;

create function public.commit_dufynd_content7_result_v1(p_task_id text,p_token uuid,p_value jsonb)
returns boolean language plpgsql security invoker set search_path=public as $$
declare
 t public.dufynd_autonomy_tasks; h public.dufynd_handler_contracts;
 rid text; r text; k text; context jsonb; saved jsonb; predecessor jsonb;
 expected_deps jsonb; hashes jsonb:='{}'; d text; result jsonb; n integer;
begin
 -- Match the existing claim/reconcile lock order. Locks survive through result
 -- INSERT, verifying, done and lease release: either ALL commit or ALL roll back.
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 select * into t from public.dufynd_autonomy_tasks where task_id=p_task_id for update;
 r:=t.durable_payload->>'role'; rid:=t.durable_payload->>'round_id';
 if t.task_id is null or r not in ('W1','W2','W3','W4','W5','W6','W7') or r is null
 or rid is null or rid !~ '^dufynd_editorial_[a-z0-9_]{6,100}$'
 or t.task_id is distinct from 'content7:'||rid||':'||r
 or p_token is null or t.lease_token is distinct from p_token
 or t.worker_owner is distinct from 'seven_content_editorial_free_v1'
 or t.domain is distinct from 'content' or t.budget_class is distinct from 'free'
 or t.provider_cost_unknown is distinct from false or t.requires_human_approval is distinct from false
 or t.external_review_required is distinct from false or t.needs_freshness_recheck is distinct from false
 or t.approval_action_type is distinct from 'auto_allowed'
 or t.durability_policy is distinct from 'durable'
 or t.resource_scope is distinct from jsonb_build_array('db:dufynd.content7.'||rid||'.'||r)
 then return false; end if;
 select * into h from public.dufynd_handler_contracts
 where handler_id='seven_content_'||lower(r)||'_v1' and handler_version='1' for share;
 if h.handler_id is null or not h.enabled or h.contract->>'cost_class' is distinct from 'free'
 or h.contract->>'certification_status' is distinct from 'certified'
 or t.required_capabilities is distinct from h.contract->'required_capabilities'
 or t.forbidden_actions is distinct from h.contract->'forbidden_actions'
 then return false; end if;
 select coalesce(jsonb_agg('content7:'||rid||':'||value),'[]') into expected_deps
 from jsonb_array_elements_text(public.dufynd_content7_dependencies_v1(r));
 if t.dependencies is distinct from expected_deps then return false; end if;
 if t.durable_payload is distinct from jsonb_build_object(
  'kind','seven_content_role_v1','version',1,'role',r,'round_id',rid,
  'source_key','content.seven_worker_editorial_pilot_20261011_v1',
  'source_sha256',p_value->>'source_sha256',
  'context_key','content.seven_workers.runtime.source.'||rid,
  'handler_id','seven_content_'||lower(r)||'_v1','provider_execution',false)
 then return false; end if;
 -- A separately approved activation must pin this full PRIVATE source/freeze
 -- snapshot before any task is ready. It is not populated by this migration.
 select value into context from public.dufynd_master_status
 where key='content.seven_workers.runtime.source.'||rid for share;
 if context is null or context->>'round' is distinct from rid
 or public.dufynd_content7_sha_v1(context) is distinct from p_value->>'source_sha256'
 then raise exception 'source_snapshot_mismatch'; end if;
 if jsonb_typeof(p_value) is distinct from 'object' or octet_length(p_value::text)>250000
 or p_value->'schema_version' is distinct from '1'::jsonb
 or p_value->'role_version' is distinct from '1'::jsonb
 or p_value->>'task_id' is distinct from t.task_id or p_value->>'round_id' is distinct from rid
 or p_value->>'role' is distinct from r or p_value->'cost_eur' is distinct from '0'::jsonb
 or p_value->'approved_for_publication' is distinct from 'false'::jsonb
 or p_value->'visual_quality_verified' is distinct from 'false'::jsonb
 or public.dufynd_content7_sha_v1(p_value->'packet') is distinct from p_value->>'packet_sha256'
 then raise exception 'invalid_result_envelope'; end if;
 result:=p_value->'packet';
 if result->>'state' is null or result->>'state' not in ('DONE','DONE_WITH_HOLDS')
 or result->'cost_eur' is distinct from '0'::jsonb
 or jsonb_typeof(result->'holds') is distinct from 'array'
 or jsonb_typeof(result->'output') is distinct from 'object'
 then raise exception 'unaccepted_worker_result'; end if;
 for d in select jsonb_array_elements_text(public.dufynd_content7_dependencies_v1(r)) loop
  select value into predecessor from public.dufynd_master_status
  where key='content.seven_workers.runtime.'||rid||'.'||d for share;
  if predecessor is null or predecessor->>'source_sha256' is distinct from p_value->>'source_sha256'
  or public.dufynd_content7_sha_v1(predecessor->'packet') is distinct from predecessor->>'packet_sha256'
  or not exists(select 1 from public.dufynd_autonomy_tasks
    where task_id='content7:'||rid||':'||d and status='done' and worker_state='done')
  then raise exception 'predecessor_not_verified'; end if;
  hashes:=hashes||jsonb_build_object(d,predecessor->>'packet_sha256');
 end loop;
 if p_value->'predecessor_sha256' is distinct from hashes then raise exception 'predecessor_hash_mismatch'; end if;
 -- Server-side output gates defend against bypassing the Python validator.
 if r in ('W4','W5','W6','W2','W7') then
  n:=case r when 'W4' then 5 when 'W5' then 10 when 'W6' then 20 when 'W2' then 10 else 30 end;
  d:=case r when 'W4' then 'fact_candidates' when 'W5' then 'questions' when 'W6' then 'hooks' when 'W2' then 'ideas' else 'slots' end;
  if jsonb_typeof(result->'output'->d) is distinct from 'array'
  or jsonb_array_length(result->'output'->d)<>n then raise exception 'role_output_count_mismatch'; end if;
 end if;
 if r='W2' then
  if exists(select 1 from jsonb_array_elements(result#>'{output,ideas}') idea
   where not ((context#>'{pilot,W6,hooks}') ? (idea->>'hook'))
   or not ((context#>'{pilot,W5,questions}') ? (idea->>'community_question'))
   or idea->'publication_approval' is distinct from 'false'::jsonb
   or idea->'creative_approval' is distinct from 'false'::jsonb
   or idea->'asset_created' is distinct from 'false'::jsonb
   or idea->'visual_score' is distinct from 'null'::jsonb)
  then raise exception 'invalid_writer_crosslink_or_approval'; end if;
 end if;
 if r='W7' then
  if (select count(distinct slot->>'date') from jsonb_array_elements(result#>'{output,slots}') slot)<>30
  or exists(select 1 from jsonb_array_elements(result#>'{output,slots}') with ordinality o(slot,n)
   where slot->>'date' is distinct from context#>>array['pilot','W7','calendar',(o.n-1)::text,'date']
   or slot->>'idea' is distinct from context#>>array['pilot','W7','calendar',(o.n-1)::text,'idea']
   or slot->>'hook' is distinct from context#>>array['pilot','W7','calendar',(o.n-1)::text,'hook'])
  then raise exception 'calendar_source_mismatch'; end if;
  if exists(select 1 from jsonb_array_elements(result#>'{output,slots}') slot
   where slot->'scheduled' is distinct from 'false'::jsonb
   or slot->'published' is distinct from 'false'::jsonb
   or slot->'owner_publication_go' is distinct from 'false'::jsonb
   or lower(btrim(coalesce(slot->>'hook',''))) ~ '(preserve frozen original text|draft a distinct hook|^tbd$|^todo$|^pending$|placeholder|platzhalter|lorem ipsum|hook folgt|hook später|insert hook)'
   or (slot->>'slot_state'='FROZEN_REFERENCE_ONLY' and (coalesce(slot->>'hook','')<>''
       or coalesce(slot->>'frozen_sha256','') !~ '^[a-f0-9]{64}$'))
   or (coalesce(slot->>'hook','')='' and (
    slot->>'slot_state' is distinct from 'FROZEN_REFERENCE_ONLY'
    or context#>>array['existing','frozen_refs',slot->>'frozen_ref','record_sha256'] is null
    or context#>>array['existing','frozen_refs',slot->>'frozen_ref','record_sha256'] is distinct from slot->>'frozen_sha256')))
  then raise exception 'invalid_calendar_or_approval'; end if;
 end if;
 k:='content.seven_workers.runtime.'||rid||'.'||r;
 select value into saved from public.dufynd_master_status where key=k for update;
 -- A lost HTTP response after successful commit is an exact receipt replay,
 -- never a second result write. Wrong tokens and changed bytes still fail.
 if saved is not null then
  if saved is not distinct from p_value and t.status='done' and t.worker_state='done' then return true; end if;
  raise exception 'immutable_result_conflict';
 end if;
 if t.status is distinct from 'in_progress' or t.worker_state not in ('claimed','working','verifying')
 or t.released_at is not null or t.lease_expires_at is null or t.lease_expires_at<=clock_timestamp()
 then return false; end if;
 insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
 values(k,'content',p_value,80,clock_timestamp());
 if not public.update_dufynd_worker_v2(t.task_id,p_token,'verifying','Atomic content result: '||k,null)
 then raise exception 'lease_lost_before_verify'; end if;
 -- Recheck wall-clock time (now() is transaction-start time in PostgreSQL).
 if t.lease_expires_at<=clock_timestamp() then raise exception 'lease_expired_during_commit'; end if;
 if not public.update_dufynd_worker_v2(t.task_id,p_token,'done','Atomic content result: '||k,null)
 then raise exception 'lease_lost_before_done'; end if;
 return true;
end $$;

revoke all on function public.dufynd_content7_canonical_v1(jsonb),
 public.dufynd_content7_sha_v1(jsonb),public.dufynd_content7_dependencies_v1(text),
 public.commit_dufynd_content7_result_v1(text,uuid,jsonb) from public,anon,authenticated;
grant execute on function public.dufynd_content7_canonical_v1(jsonb),
 public.dufynd_content7_sha_v1(jsonb),public.dufynd_content7_dependencies_v1(text),
 public.commit_dufynd_content7_result_v1(text,uuid,jsonb) to service_role,postgres;
