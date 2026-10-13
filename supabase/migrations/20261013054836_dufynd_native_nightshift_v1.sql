-- DEVELOPMENT ONLY. No schedule, activation, approval or live task is installed.
-- Reuses autonomy_tasks, handler_contracts, master_status and Supervisor V2 leases.
alter table public.dufynd_autonomy_tasks add column nightshift_attempts smallint
 check (nightshift_attempts between 0 and 3);

create function public.dufynd_ns_v1_hash(j jsonb) returns text
language sql immutable security invoker set search_path=public as $$
 select encode(sha256(convert_to(j::text,'UTF8')),'hex');
$$;

create function public.dufynd_ns_v1_code_hash() returns text
language sql stable security invoker set search_path=public as $$
 select public.dufynd_ns_v1_hash(jsonb_agg(pg_get_functiondef(p.oid) order by p.proname))
 from pg_proc p join pg_namespace n on n.oid=p.pronamespace
 where n.nspname='public' and starts_with(p.proname,'dufynd_ns_v1_');
$$;

-- Only database-resident, explicitly named evidence. No caller-supplied content,
-- repository paths, model tools, HTTP, analytics writes or publication dispatch.
create function public.dufynd_ns_v1_manifest(p_start timestamptz,p_end timestamptz)
returns jsonb language plpgsql security invoker set search_path=public set timezone='UTC' as $$
declare items jsonb:='[]'; src jsonb; packet jsonb; hid text; sk text; h jsonb; seen timestamptz;
begin
 if p_start is null or p_end is null or not isfinite(p_start) or not isfinite(p_end)
 or p_end<=p_start or p_end>p_start+interval '1 hour' then
  raise exception 'nightshift_window_invalid';
 end if;
 for hid,sk in values
 ('nightshift_measurement_qa','jarvis.first_money_measurement_v1'),
 ('nightshift_receipt_qa','jarvis.mission_result.v1:autonomy_acceptance_20261010:2') loop
  select value,last_verified_at into src,seen from public.dufynd_master_status where key=sk;
  if jsonb_typeof(src) is distinct from 'object' or octet_length(src::text)>16384 then
   raise exception 'nightshift_source_missing_or_oversize';
  end if;
  select contract into h from public.dufynd_handler_contracts
   where handler_id=hid and handler_version='1';
  -- Preserve exactly the fields evaluated by these fixed handlers; timestamps are
  -- provenance, not a reason to repeat unchanged semantic work every night.
  if hid='nightshift_measurement_qa' then
   select jsonb_object_agg(key,value) into packet from jsonb_each(src)
    where key in ('version','traffic_provenance','clickout_is_sale','new_spend_usd',
      'internal_qa_events','unclassified_events','postlaunch_landing_sessions',
      'postlaunch_product_views','postlaunch_offer_views','postlaunch_merchant_clickouts',
      'network_ingestion_connected','experiment_id','content_id');
  else
   packet:=jsonb_build_object('artifact',src->'artifact','artifact_md5',src->'artifact_md5',
    'quality_verified',src->'quality_verified','lease_released',src->'lease_released',
    'task_id',src->'task_id');
  end if;
  packet:=jsonb_build_object('kind','native_nightshift_v1','handler',hid,'version','1',
   'source_key',sk,'input',packet,'contract_sha256',public.dufynd_ns_v1_hash(h));
  items:=items||jsonb_build_array(jsonb_build_object(
   'task_id','nightshift:v1:'||public.dufynd_ns_v1_hash(packet), 'packet',packet,
   'source_record_sha256',public.dufynd_ns_v1_hash(src),'source_verified_at',seen));
 end loop;
 return jsonb_build_object('version',1,'goal','zero_cost_native_nightshift_v1',
  'repository','tncommerce/commerce-agents','starts_at',p_start,'ends_at',p_end,
  'code_sha256',public.dufynd_ns_v1_code_hash(),'new_spend_usd',0,'paid_calls',0,
  'max_attempts_per_task',3,'max_total_attempts',6,'max_tasks',2,
  'max_statement_ms',120000,'lease_seconds',180,'items',items,
  'cron_baseline',(select jsonb_agg(to_jsonb(j) order by jobid) from cron.job j),
  'holds',jsonb_build_array(jsonb_build_object('kind','awin_original_transactions',
    'state','OWNER_HOLD','reason','original_network_transaction_report_required')));
end $$;

-- The approved manifest hash is supplied ONLY through the existing owner decision
-- record. Preview is read-only; enqueue cannot invent or approve a decision.
create function public.dufynd_ns_v1_start(p_id text,p_decision text)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare d jsonb; m jsonb; old jsonb; x jsonb; k text; packet jsonb; hid text;
begin
 if p_id is null or p_id !~ '^[a-z0-9_]{1,48}$' then raise exception 'nightshift_id_invalid'; end if;
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 perform pg_advisory_xact_lock(hashtext('dufynd-native-nightshift-v1'));
 k:='jarvis.mission.v1:native_'||p_id;
 select value into old from public.dufynd_master_status where key=k;
 if old is not null then
  if old->>'decision_id' is distinct from p_decision then raise exception 'nightshift_id_conflict'; end if;
  return old;
 end if;
 select decision into d from public.dufynd_human_decisions
 where decision_id=p_decision and status='approved';
 if d->>'scope' is distinct from 'dufynd_native_nightshift_v1' then
  raise exception 'nightshift_exact_owner_approval_required';
 end if;
 m:=public.dufynd_ns_v1_manifest((d->>'starts_at')::timestamptz,(d->>'ends_at')::timestamptz);
 if d->>'manifest_sha256' is distinct from public.dufynd_ns_v1_hash(m)
 or (m->>'ends_at')::timestamptz<=clock_timestamp()
 or (m->>'starts_at')::timestamptz>clock_timestamp()+interval '24 hours' then
  raise exception 'nightshift_approval_stale_or_mismatched';
 end if;
 if exists(select from public.dufynd_master_status where starts_with(key,'jarvis.mission.v1:native_')
  and value->>'state' in ('native_ready','native_running','native_stopped')
  and public.dufynd_parse_timestamp(value#>>'{definition,ends_at}')>clock_timestamp()) then
  raise exception 'nightshift_existing_mission_resume_required';
 end if;
 for x in select value from jsonb_array_elements(m->'items') loop
  packet:=x->'packet'; hid:=packet->>'handler';
  insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,priority,
   budget_class,resource_scope,durability_policy,durable_payload,required_capabilities,
   forbidden_actions,nightshift_attempts)
  values(x->>'task_id','supervisor','Bounded native Nightshift evidence QA',
   'Validate the approved database snapshot only; no external action or revenue inference.',
   'ready',30,'free','["db:dufynd.native_nightshift"]','durable',packet,
   '["supabase.task_state"]','["gmail.send","social.publish","budget.spend","main.merge","commerce.activate","shell.execute"]',0)
  on conflict(task_id) do nothing;
  if not exists(select from public.dufynd_autonomy_tasks where task_id=x->>'task_id'
   and durable_payload=packet and nightshift_attempts between 0 and 3) then
   raise exception 'nightshift_existing_task_conflict';
  end if;
 end loop;
 old:=jsonb_build_object('goal','zero_cost_native_nightshift_v1','state','native_ready',
  'definition',m,'definition_sha256',public.dufynd_ns_v1_hash(m),'decision_id',p_decision,
  'created_at',clock_timestamp(),'stop_reason',null);
 insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
 values(k,'jarvis',old,100,clock_timestamp());
 return old;
end $$;

-- Ordinary writes cannot erase deduplication receipts, reset attempts, alter the
-- approved manifest or retarget a native task. PostgreSQL administrators remain
-- trusted: disabled triggers or changed function definitions are not signatures.
create function public.dufynd_ns_v1_guard() returns trigger
language plpgsql security invoker set search_path=public as $$
begin
 if tg_table_name='dufynd_autonomy_tasks' then
  if old.task_id like 'nightshift:v1:%' then
   if tg_op='DELETE' then raise exception 'nightshift_task_immutable'; end if;
   if (new.task_id,new.domain,new.durable_payload,new.resource_scope,new.durability_policy,
       new.required_capabilities,new.forbidden_actions)
    is distinct from (old.task_id,old.domain,old.durable_payload,old.resource_scope,old.durability_policy,
       old.required_capabilities,old.forbidden_actions)
    or new.nightshift_attempts is null or new.nightshift_attempts<old.nightshift_attempts
    or new.nightshift_attempts>old.nightshift_attempts+1 then
    raise exception 'nightshift_task_immutable';
   end if;
  end if;
 else
  if old.key like 'jarvis.mission_result.v1:native:%' then
   if tg_op='DELETE' or new is distinct from old then raise exception 'nightshift_result_immutable'; end if;
  elsif starts_with(old.key,'jarvis.mission.v1:native_') then
   if tg_op='DELETE' then raise exception 'nightshift_checkpoint_immutable'; end if;
   if new.key<>old.key or (new.value->'definition',new.value->'definition_sha256',new.value->'decision_id')
    is distinct from (old.value->'definition',old.value->'definition_sha256',old.value->'decision_id') then
    raise exception 'nightshift_definition_immutable';
   end if;
  elsif starts_with(old.key,'jarvis.native_nightshift_v1.pilot:') then
   if tg_op='DELETE' then raise exception 'nightshift_pilot_immutable'; end if;
   if new.key<>old.key or (new.value->'definition',new.value->'definition_sha256')
    is distinct from (old.value->'definition',old.value->'definition_sha256') then
    raise exception 'nightshift_pilot_immutable';
   end if;
  end if;
 end if;
 if tg_op='DELETE' then return old; end if;
 return new;
end $$;
create trigger dufynd_ns_task_guard before update or delete on public.dufynd_autonomy_tasks
 for each row execute function public.dufynd_ns_v1_guard();
create trigger dufynd_ns_status_guard before update or delete on public.dufynd_master_status
 for each row execute function public.dufynd_ns_v1_guard();

create function public.dufynd_ns_v1_gate(m jsonb) returns text
language plpgsql stable security invoker set search_path=public as $$
declare c jsonb; d jsonb; p jsonb; ms numeric;
begin
 select value into c from public.dufynd_master_status where key='jarvis.native_nightshift_v1.config';
 if c->'enabled' is distinct from 'true'::jsonb then return 'disabled'; end if;
 if c->'stop' is distinct from 'false'::jsonb then return 'stop_requested'; end if;
 if c ? 'pilot_key' then
  select value into p from public.dufynd_master_status where key=c->>'pilot_key';
  if p->>'state' is distinct from 'armed'
  or p->>'definition_sha256' is distinct from public.dufynd_ns_v1_hash(p->'definition')
  or p#>>'{definition,manifest_sha256}' is distinct from m->>'definition_sha256'
  then return 'pilot_not_armed'; end if;
 end if;
 d:=m->'definition';
 if m->>'definition_sha256' is distinct from public.dufynd_ns_v1_hash(d)
 or d->>'code_sha256' is distinct from public.dufynd_ns_v1_code_hash()
 or d->>'goal' is distinct from 'zero_cost_native_nightshift_v1'
 or d->'new_spend_usd' is distinct from '0'::jsonb or d->'paid_calls' is distinct from '0'::jsonb
 or d->'max_tasks' is distinct from '2'::jsonb or d->'max_total_attempts' is distinct from '6'::jsonb
 or d->'max_attempts_per_task' is distinct from '3'::jsonb
 or jsonb_typeof(d->'items') is distinct from 'array' then return 'checkpoint_corrupt'; end if;
 if jsonb_array_length(d->'items')<>2 then return 'checkpoint_corrupt'; end if;
 if not exists(select from public.dufynd_human_decisions where decision_id=m->>'decision_id'
  and status='approved' and decision->>'scope'='dufynd_native_nightshift_v1'
  and decision->>'manifest_sha256'=m->>'definition_sha256') then return 'owner_approval_revoked'; end if;
 if public.dufynd_parse_timestamp(d->>'starts_at') is null
 or public.dufynd_parse_timestamp(d->>'ends_at') is null then return 'checkpoint_corrupt'; end if;
 if clock_timestamp()<(d->>'starts_at')::timestamptz then return 'not_due'; end if;
 if clock_timestamp()>=(d->>'ends_at')::timestamptz then return 'window_closed'; end if;
 -- A hard server-side statement deadline must exist BEFORE the top-level CALL.
 -- SET inside a running SQL function does not arm that statement's timeout.
 ms:=extract(epoch from current_setting('statement_timeout')::interval)*1000;
 if ms<=0 or ms>120000 then return 'statement_timeout_unbounded'; end if;
 return null;
exception when others then return 'checkpoint_corrupt';
end $$;

create function public.dufynd_ns_v1_task_valid(t public.dufynd_autonomy_tasks,packet jsonb)
returns boolean language sql stable security invoker set search_path=public as $$
 select coalesce(t.durable_payload=packet and t.task_id='nightshift:v1:'||public.dufynd_ns_v1_hash(packet)
  and t.domain='supervisor' and t.budget_class='free' and not t.provider_cost_unknown
  and not t.requires_human_approval and not t.external_review_required and not t.needs_freshness_recheck
  and t.dependencies='[]'::jsonb and t.resource_scope='["db:dufynd.native_nightshift"]'::jsonb
  and t.durability_policy='durable' and t.nightshift_attempts between 0 and 3
  and packet->>'kind'='native_nightshift_v1' and packet->>'version'='1'
  and packet->>'handler' in ('nightshift_measurement_qa','nightshift_receipt_qa')
  and exists(select from public.dufynd_handler_contracts h
   where h.handler_id=packet->>'handler' and h.handler_version='1' and h.enabled
    and h.contract->>'cost_class'='free' and h.contract->>'certification_status'='certified'
    and h.contract->>'code_sha256'=public.dufynd_ns_v1_code_hash()
    and public.dufynd_ns_v1_hash(h.contract)=packet->>'contract_sha256'),false);
$$;

create function public.dufynd_ns_v1_claim() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare k text; m jsonb; x jsonb; t public.dufynd_autonomy_tasks; token uuid;
 gate text; claimed jsonb; result jsonb; remaining boolean:=false; summary jsonb;
begin
 if not pg_try_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'))
 or not pg_try_advisory_xact_lock(hashtext('dufynd-native-nightshift-v1')) then
  return jsonb_build_object('state','busy');
 end if;
 select key,value into k,m from public.dufynd_master_status
 where starts_with(key,'jarvis.mission.v1:native_') and value->>'state' in ('native_ready','native_running','native_stopped')
 order by last_verified_at,key limit 1 for update skip locked;
 if k is null then return jsonb_build_object('state','idle'); end if;
 gate:=public.dufynd_ns_v1_gate(m);
 if gate is not null then
  update public.dufynd_master_status set value=value||jsonb_build_object(
   'state',case when gate in ('disabled','stop_requested','not_due','statement_timeout_unbounded')
    then 'native_stopped' else 'native_blocked' end,'stop_reason',gate),last_verified_at=clock_timestamp() where key=k;
  return jsonb_build_object('state',gate);
 end if;
 -- All recovery uses the existing supervisor; its fencing and retry policy remain.
 perform public.reconcile_dufynd_supervisor_v2();
 for x in select value from jsonb_array_elements(m#>'{definition,items}') loop
  select * into t from public.dufynd_autonomy_tasks where task_id=x->>'task_id' for update;
  if t.task_id is null then
   gate:='task_missing'; exit;
  end if;
  if t.requires_human_approval or t.status='waiting_human_input' then continue; end if;
  if not public.dufynd_ns_v1_task_valid(t,x->'packet') then gate:='task_contract_invalid'; exit; end if;
  select value into result from public.dufynd_master_status
   where key='jarvis.mission_result.v1:native:'||t.task_id;
  if t.status='done' then
   if result->>'packet_sha256' is distinct from public.dufynd_ns_v1_hash(t.durable_payload)
    or result->>'artifact_sha256' is distinct from public.dufynd_ns_v1_hash(result->'artifact') then
    gate:='result_missing_or_corrupt'; exit;
   end if;
   continue;
  end if;
  if result is not null then gate:='unexpected_result'; exit; end if;
  if t.nightshift_attempts>=3 or t.status='blocked' then continue; end if;
  remaining:=true;
  if t.released_at is null and t.lease_expires_at>clock_timestamp() then continue; end if;
  if t.status<>'ready' then continue; end if;
  token:=gen_random_uuid();
  claimed:=public.claim_dufynd_worker_v2(t.task_id,'native_nightshift_v1',token);
  if claimed is null then continue; end if;
  perform set_config('dufynd.worker_write',token::text,true);
  update public.dufynd_autonomy_tasks set nightshift_attempts=nightshift_attempts+1
   where task_id=t.task_id;
  perform set_config('dufynd.worker_write','',true);
  update public.dufynd_master_status set value=value||jsonb_build_object('state','native_running',
   'stop_reason',null),last_verified_at=clock_timestamp() where key=k;
  return jsonb_build_object('state','claimed','mission_key',k,'task_id',t.task_id,
   'token',token,'attempt',t.nightshift_attempts+1);
 end loop;
 select jsonb_build_object('done',count(*) filter(where q.status='done'),
  'owner_hold',count(*) filter(where q.requires_human_approval or q.status='waiting_human_input'),
  'failed_or_exhausted',count(*) filter(where q.status='blocked' or (q.nightshift_attempts>=3 and q.status<>'done')),
  'attempts',coalesce(sum(q.nightshift_attempts),0),'awin_original_report','OWNER_HOLD') into summary
 from public.dufynd_autonomy_tasks q where q.task_id in
  (select value->>'task_id' from jsonb_array_elements(m#>'{definition,items}'));
 update public.dufynd_master_status set value=value||jsonb_build_object(
  'state',case when gate is not null then 'native_blocked' when remaining then 'native_ready' else 'native_completed' end,
  'summary',summary,'stop_reason',coalesce(gate,case when remaining then 'waiting_lease_or_dependency' else 'bounded_queue_terminal' end)),
  last_verified_at=clock_timestamp() where key=k;
 return jsonb_build_object('state',coalesce(gate,case when remaining then 'waiting' else 'terminal' end));
end $$;

create function public.dufynd_ns_v1_evaluate(packet jsonb) returns jsonb
language plpgsql immutable security invoker set search_path=public as $$
declare j jsonb:=packet->'input'; findings jsonb:='[]'; n text;
begin
 if packet->>'version' is distinct from '1' then raise exception 'handler_version_denied'; end if;
 if packet->>'handler'='nightshift_measurement_qa' then
  if j->'version' is distinct from '2'::jsonb
   or j->>'traffic_provenance' is distinct from 'visitor_class_excludes_qa_sessions_and_unclassified_history'
   or j->'clickout_is_sale' is distinct from 'false'::jsonb
   or j->'new_spend_usd' is distinct from '0'::jsonb then
   findings:=findings||'"measurement_provenance_or_sale_guard_invalid"'::jsonb;
  end if;
  foreach n in array array['internal_qa_events','unclassified_events','postlaunch_landing_sessions',
   'postlaunch_product_views','postlaunch_offer_views','postlaunch_merchant_clickouts'] loop
   if jsonb_typeof(j->n) is distinct from 'number' or coalesce(j->>n,'') !~ '^[0-9]{1,12}$' then
    findings:=findings||to_jsonb('invalid_count:'||n);
   end if;
  end loop;
 elsif packet->>'handler'='nightshift_receipt_qa' then
  if j->'quality_verified' is distinct from 'true'::jsonb or j->'lease_released' is distinct from 'true'::jsonb
   or j->>'artifact_md5' is distinct from md5((j->'artifact')::text)
   or j#>'{artifact,publishing_allowed}' is distinct from 'false'::jsonb
   or j#>'{artifact,paid_generation_allowed}' is distinct from 'false'::jsonb
   or j#>'{artifact,new_spend_usd}' is distinct from '0'::jsonb then
   findings:=findings||'"archived_receipt_integrity_or_safety_invalid"'::jsonb;
  end if;
 else raise exception 'handler_denied'; end if;
 return jsonb_build_object('version',1,'handler',packet->>'handler','findings',findings,
  'source_kind','approved_archived_database_snapshot','live_business_qa',false,
  'revenue','UNKNOWN','commission','UNKNOWN','original_awin_report_available',false,
  'publishing_allowed',false,'paid_calls',0,'new_spend_usd',0);
end $$;

create function public.dufynd_ns_v1_finish(p_mission text,p_task text,p_token uuid)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare m jsonb; t public.dufynd_autonomy_tasks; x jsonb; a jsonb; r jsonb; gate text;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 perform pg_advisory_xact_lock(hashtext('dufynd-native-nightshift-v1'));
 select value into m from public.dufynd_master_status where key=p_mission for update;
 select * into t from public.dufynd_autonomy_tasks where task_id=p_task for update;
 if t.lease_token is distinct from p_token or p_token is null or t.released_at is not null
 or t.lease_expires_at<=clock_timestamp() or t.worker_owner is distinct from 'native_nightshift_v1'
 or t.worker_state not in ('claimed','working','verifying') then
  return jsonb_build_object('state','stale_fence');
 end if;
 gate:=public.dufynd_ns_v1_gate(m);
 select value into x from jsonb_array_elements(m#>'{definition,items}') where value->>'task_id'=p_task;
 if gate is null and not public.dufynd_ns_v1_task_valid(t,x->'packet') then gate:='task_contract_invalid'; end if;
 if gate is not null then
  perform public.update_dufynd_worker_v2(p_task,p_token,'queued',null,gate);
  return jsonb_build_object('state',gate);
 end if;
 begin
  if not public.update_dufynd_worker_v2(p_task,p_token,'working',null,null) then raise exception 'working_fence'; end if;
  a:=public.dufynd_ns_v1_evaluate(t.durable_payload);
  if clock_timestamp()>=least(t.lease_expires_at,(m#>>'{definition,ends_at}')::timestamptz) then
   raise exception 'runtime_deadline';
  end if;
  r:=jsonb_build_object('task_id',p_task,'mission_key',p_mission,'decision_id',m->>'decision_id',
   'definition_sha256',m->>'definition_sha256','packet_sha256',public.dufynd_ns_v1_hash(t.durable_payload),
   'source_record_sha256',x->>'source_record_sha256','source_verified_at',x->'source_verified_at',
   'artifact',a,'artifact_sha256',public.dufynd_ns_v1_hash(a),'completed_at',clock_timestamp());
  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
   values('jarvis.mission_result.v1:native:'||p_task,'jarvis',r,90,clock_timestamp());
  if not public.update_dufynd_worker_v2(p_task,p_token,'verifying',r::text,null)
   or not public.update_dufynd_worker_v2(p_task,p_token,'done',r::text,null) then raise exception 'completion_fence'; end if;
  update public.dufynd_master_status set value=value||jsonb_build_object('last_result',p_task),
   last_verified_at=clock_timestamp() where key=p_mission;
  return jsonb_build_object('state','done','task_id',p_task,'artifact',a);
 exception when others then
  perform public.update_dufynd_worker_v2(p_task,p_token,
   case when t.nightshift_attempts>=3 then 'failed_terminal' else 'failed_retryable' end,
   'native_step_failed_'||sqlstate,'native_handler_failed');
  return jsonb_build_object('state','failed','code',sqlstate);
 end;
end $$;

-- Arming and restoring use pg_cron's public API, never direct cron table writes.
-- The Owner-approved manifest binds ALL eleven registrations before arming.
create function public.dufynd_ns_v1_pilot_arm(p_id text) returns jsonb
language plpgsql security invoker set search_path=public as $$
declare m jsonb; b jsonb; j jsonb; p jsonb; k text;
begin
 if current_setting('transaction_isolation')<>'serializable' then
  raise exception 'pilot_serializable_transaction_required';
 end if;
 perform pg_advisory_xact_lock(hashtext('dufynd-native-nightshift-v1'));
 k:='jarvis.native_nightshift_v1.pilot:'||p_id;
 select value into p from public.dufynd_master_status where key=k;
 if p is not null then return p; end if; -- Never extend/rearm a used pilot.
 if exists(select from public.dufynd_master_status
  where starts_with(key,'jarvis.native_nightshift_v1.pilot:')
  and value->>'state' is distinct from 'restored') then raise exception 'pilot_restore_required'; end if;
 select value into m from public.dufynd_master_status where key='jarvis.mission.v1:native_'||p_id;
 if m is null or m->>'definition_sha256' is distinct from public.dufynd_ns_v1_hash(m->'definition')
 or m#>>'{definition,code_sha256}' is distinct from public.dufynd_ns_v1_code_hash()
 or (m#>>'{definition,ends_at}')::timestamptz-(m#>>'{definition,starts_at}')::timestamptz<>interval '45 minutes'
 or (m#>>'{definition,ends_at}')::timestamptz<=clock_timestamp()
 or not exists(select from public.dufynd_human_decisions where decision_id=m->>'decision_id'
  and status='approved' and decision->>'manifest_sha256'=m->>'definition_sha256'
  and decision->>'scope'='dufynd_native_nightshift_v1') then raise exception 'pilot_exact_approval_required'; end if;
 select jsonb_agg(to_jsonb(c) order by jobid) into b from cron.job c;
 select to_jsonb(c) into j from cron.job c where jobid=11;
 if b is distinct from m#>'{definition,cron_baseline}' or jsonb_array_length(b)<>11
 or (select array_agg(jobid order by jobid) from cron.job) is distinct from array[1,2,3,4,5,6,7,8,9,10,11]::bigint[]
 or exists(select from cron.job where not active)
 or j->>'jobname' is distinct from 'dufynd-ceo-v2-growth-loop'
 or j->>'command' is distinct from 'select public.run_dufynd_ceo_with_missions_v1();'
 or j->>'database' is distinct from current_database() or j->>'username' is distinct from current_user
 then raise exception 'pilot_cron_baseline_changed'; end if;
 p:=jsonb_build_object('mission_key','jarvis.mission.v1:native_'||p_id,
  'manifest_sha256',m->>'definition_sha256','starts_at',m#>'{definition,starts_at}',
  'ends_at',m#>'{definition,ends_at}','cron_baseline',b);
 p:=jsonb_build_object('definition',p,'definition_sha256',public.dufynd_ns_v1_hash(p),
  'state','armed','restore_attempts',0,'armed_at',clock_timestamp());
 insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
 values(k,'jarvis',p,100,clock_timestamp());
 update public.dufynd_handler_contracts set enabled=true
 where handler_id in ('nightshift_measurement_qa','nightshift_receipt_qa') and handler_version='1';
 update public.dufynd_master_status set value=jsonb_build_object('enabled',true,'stop',false,'pilot_key',k)
 where key='jarvis.native_nightshift_v1.config';
 perform cron.alter_job(11,command:='CALL public.dufynd_ns_v1_cycle();');
 return p;
end $$;

-- This transaction commits the safety stop BEFORE any fallible restoration or
-- legacy business action. A later failed transaction cannot re-enable work.
create function public.dufynd_ns_v1_pilot_poll(p_abort boolean default false) returns boolean
language plpgsql security invoker set search_path=public as $$
declare p jsonb; m jsonb; k text; why text; b jsonb; expected jsonb;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-native-nightshift-v1'));
 select key,value into k,p from public.dufynd_master_status
 where starts_with(key,'jarvis.native_nightshift_v1.pilot:')
 order by last_verified_at desc,key limit 1 for update;
 if p is null then why:='pilot_checkpoint_missing';
 elsif p->>'state' is distinct from 'armed' then why:=coalesce(p->>'stop_reason','pilot_not_armed');
 elsif p_abort then why:='operator_abort';
 elsif p->>'definition_sha256' is distinct from public.dufynd_ns_v1_hash(p->'definition') then why:='pilot_checkpoint_corrupt';
 else
  select value into m from public.dufynd_master_status where key=p#>>'{definition,mission_key}';
  why:=public.dufynd_ns_v1_gate(m);
  if why='not_due' then why:=null; end if;
  if m->>'definition_sha256' is distinct from p#>>'{definition,manifest_sha256}' then why:='pilot_manifest_changed'; end if;
  select jsonb_agg(to_jsonb(j) order by jobid) into b from cron.job j;
  select jsonb_agg(case when x->>'jobid'='11' then jsonb_set(x,'{command}',to_jsonb('CALL public.dufynd_ns_v1_cycle();'::text)) else x end order by (x->>'jobid')::bigint)
   into expected from jsonb_array_elements(p#>'{definition,cron_baseline}') x;
  if b is distinct from expected then why:='pilot_cron_drift'; end if;
 end if;
 if why is null then return true; end if;
 update public.dufynd_master_status set value=value||'{"enabled":false,"stop":true}'::jsonb,
  last_verified_at=clock_timestamp() where key='jarvis.native_nightshift_v1.config';
 update public.dufynd_handler_contracts set enabled=false
 where handler_id in ('nightshift_measurement_qa','nightshift_receipt_qa') and handler_version='1';
 if k is not null and p->>'state'='armed' then
  update public.dufynd_master_status set value=value||jsonb_build_object('state','restoring','stop_reason',why,'stopped_at',clock_timestamp()),
   last_verified_at=clock_timestamp() where key=k;
 end if;
 return false;
end $$;

create function public.dufynd_ns_v1_pilot_restore() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare p jsonb; k text; j jsonb; b jsonb; outcome jsonb; attempts integer;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-native-nightshift-v1'));
 select key,value into k,p from public.dufynd_master_status
 where starts_with(key,'jarvis.native_nightshift_v1.pilot:')
 order by last_verified_at desc,key limit 1 for update;
 if p->>'state' in ('armed','restored') then return p; end if;
 -- Missing checkpoint still restores the one hard-coded known CEO command;
 -- never trusts a stored arbitrary SQL string. Identity drift needs an operator.
 if p is null then
  select value into outcome from public.dufynd_master_status where key='jarvis.native_nightshift_v1.recovery';
 end if;
 attempts:=case when coalesce(p->>'restore_attempts',outcome->>'restore_attempts') ~ '^[0-3]$'
  then coalesce(p->>'restore_attempts',outcome->>'restore_attempts')::integer else 0 end;
 if attempts>=3 then return jsonb_build_object('state','OWNER_HOLD','reason','restore_attempts_exhausted'); end if;
 begin
  if current_setting('transaction_isolation')<>'serializable' then
   raise exception 'pilot_serializable_transaction_required';
  end if;
  select to_jsonb(c) into j from cron.job c where jobid=11;
  if j->>'jobname' is distinct from 'dufynd-ceo-v2-growth-loop'
  or j->>'database' is distinct from current_database() or j->>'username' is distinct from current_user
  or j->'active' is distinct from 'true'::jsonb
  or j->>'command' not in ('CALL public.dufynd_ns_v1_cycle();','select public.run_dufynd_ceo_with_missions_v1();')
  then raise exception 'pilot_restore_identity_drift'; end if;
  if j->>'command'='CALL public.dufynd_ns_v1_cycle();' then
   perform cron.alter_job(11,command:='select public.run_dufynd_ceo_with_missions_v1();');
  end if;
  select jsonb_agg(to_jsonb(c) order by jobid) into b from cron.job c;
  outcome:=jsonb_build_object('state','restored','restored_at',clock_timestamp(),
   'restore_attempts',attempts+1,'all_eleven_exact',b is not distinct from p#>'{definition,cron_baseline}');
 exception when others then
  outcome:=jsonb_build_object('state','restore_failed','restore_attempts',attempts+1,
   'error_sqlstate',sqlstate,'owner_hold',true,'failed_at',clock_timestamp());
 end;
 if k is not null then
  update public.dufynd_master_status set value=value||outcome,last_verified_at=clock_timestamp() where key=k;
 else
  insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
  values('jarvis.native_nightshift_v1.recovery','jarvis',outcome,100,clock_timestamp())
  on conflict(key) do update set value=excluded.value,last_verified_at=excluded.last_verified_at;
 end if;
 return outcome;
end $$;

-- Abort never calls the legacy business action or claims work. Safe to repeat.
create procedure public.dufynd_ns_v1_pilot_abort()
language plpgsql security invoker as $$
begin
 perform public.dufynd_ns_v1_pilot_poll(true);
 commit;
 set transaction isolation level serializable;
 begin
  perform public.dufynd_ns_v1_pilot_restore();
 exception when serialization_failure then
  raise log 'nightshift restore serialization conflict; retry on existing tick';
 end;
 commit;
end $$;

-- Top-level CALL only, NOT SELECT -> CALL and NOT an explicit transaction.
-- Existing CEO/mission work is committed first. Claim+attempt is then committed
-- BEFORE evaluation. Backend death cannot erase the reserved attempt.
create procedure public.dufynd_ns_v1_cycle()
language plpgsql security invoker as $$
declare c jsonb; armed boolean;
begin
 armed:=public.dufynd_ns_v1_pilot_poll();
 commit;
 -- Must precede even PL/pgSQL IF expression evaluation in the new transaction.
 set transaction isolation level serializable;
 if not armed then
  begin
   perform public.dufynd_ns_v1_pilot_restore();
  exception when serialization_failure then
   raise log 'nightshift restore serialization conflict; retry on existing tick';
  end;
 end if;
 commit;
 perform public.run_dufynd_ceo_with_missions_v1();
 commit;
 if not armed then return; end if;
 c:=public.dufynd_ns_v1_claim();
 commit;
 if c->>'state'='claimed' then
  perform public.dufynd_ns_v1_finish(c->>'mission_key',c->>'task_id',(c->>'token')::uuid);
  commit;
 end if;
end $$;

-- Disabled until a separately approved, hash-bound pilot. No cron DDL here.
insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
values('jarvis.native_nightshift_v1.config','jarvis','{"enabled":false,"stop":true}',100,now());
insert into public.dufynd_handler_contracts(handler_id,handler_version,contract,enabled)
select h,'1',jsonb_build_object('handler_id',h,'handler_version','1','cost_class','free',
 'certification_status','certified','risk_class','low','durability_class','durable',
 'allowed_scopes',jsonb_build_array('supervisor'),'allowed_resources',jsonb_build_array('db:dufynd.native_nightshift'),
 'required_capabilities',jsonb_build_array('supabase.task_state'),
 'allowed_tools',jsonb_build_array('dufynd_ns_v1_evaluate'),
 'forbidden_actions',jsonb_build_array('gmail.send','social.publish','budget.spend','main.merge','commerce.activate','shell.execute'),
 'code_sha256',public.dufynd_ns_v1_code_hash()),false
from unnest(array['nightshift_measurement_qa','nightshift_receipt_qa']) h;

-- Cron currently runs as postgres. Do not broaden the public API or service JWT.
do $$ declare p record; begin
 for p in select f.oid::regprocedure as signature,f.prokind from pg_proc f
  join pg_namespace n on n.oid=f.pronamespace
  where n.nspname='public' and starts_with(f.proname,'dufynd_ns_v1_') loop
  execute format('revoke all on %s %s from public,anon,authenticated,service_role',
   case when p.prokind='p' then 'procedure' else 'function' end,p.signature);
  execute format('grant execute on %s %s to postgres',
   case when p.prokind='p' then 'procedure' else 'function' end,p.signature);
 end loop;
end $$;
