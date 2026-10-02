-- Supervisor V2 extends the existing control plane. Legacy status/queue contracts
-- remain compatible; worker_state carries the detailed execution state machine.
alter table public.dufynd_autonomy_tasks
  add column if not exists worker_state text not null default 'queued',
  add column if not exists worker_owner text,
  add column if not exists lease_token uuid,
  add column if not exists started_at timestamptz,
  add column if not exists heartbeat_at timestamptz,
  add column if not exists last_progress_at timestamptz,
  add column if not exists lease_expires_at timestamptz,
  add column if not exists released_at timestamptz,
  add column if not exists expected_next_checkpoint text,
  add column if not exists retry_count integer not null default 0,
  add column if not exists blocked_reason text,
  add column if not exists resource_scope jsonb not null default '["exclusive:global"]',
  add column if not exists budget_class text not null default 'model',
  add column if not exists provider_cost_unknown boolean not null default false;

alter table public.dufynd_autonomy_tasks add constraint dufynd_worker_state_check check
  (worker_state in ('queued','ready','claimed','working','verifying','done',
   'waiting_external','waiting_human_input','blocked','failed_retryable','failed_terminal','stale'));
alter table public.dufynd_autonomy_tasks add constraint dufynd_worker_scope_check check
  (jsonb_typeof(resource_scope) = 'array' and jsonb_array_length(resource_scope) > 0);
alter table public.dufynd_autonomy_tasks add constraint dufynd_worker_retry_check check (retry_count >= 0);
alter table public.dufynd_autonomy_tasks add constraint dufynd_worker_budget_check check (budget_class in ('free','model'));
alter table public.dufynd_autonomy_tasks enable row level security;
update public.dufynd_autonomy_tasks set worker_state = case
  when status='in_progress' then 'stale'
  when status in ('done','ready','waiting_external','waiting_human_input','blocked') then status
  else 'queued' end;

create or replace function public.dufynd_parse_timestamp(p_value text)
returns timestamptz language plpgsql stable security invoker set search_path=public as $$
begin return p_value::timestamptz;
exception when others then return null; end $$;

create or replace function public.dufynd_resources_conflict(a jsonb, b jsonb)
returns boolean language sql immutable security invoker set search_path=public as $$
select jsonb_array_length(a)=0 or jsonb_array_length(b)=0
 or a ? 'exclusive:global' or b ? 'exclusive:global'
 or exists (select 1 from jsonb_array_elements_text(a) x, jsonb_array_elements_text(b) y
 where x=y or (x like 'repo:%' and y like 'repo:%' and
 (x='repo:*' or y='repo:*' or starts_with(rtrim(x,'/'),rtrim(y,'/')||'/')
 or starts_with(rtrim(y,'/'),rtrim(x,'/')||'/'))));
$$;

create or replace function public.dufynd_valid_resource_scope(p_scope jsonb)
returns boolean language sql immutable security invoker set search_path=public as $$
select jsonb_typeof(p_scope)='array' and jsonb_array_length(p_scope)>0
 and not exists(select 1 from jsonb_array_elements_text(p_scope) r
 where r is null or r !~ '^(repo|db|external|exclusive):[^[:space:]]+$'
 or r like '%..%' or position(chr(92) in r)>0 or r like '%//%'
 or (r like 'repo:%' and (substring(r from 6) like '/%' or substring(r from 6) ~ '(^|/)[.](/|$)' or (r like '%*%' and r<>'repo:*'))));
$$;
alter table public.dufynd_autonomy_tasks add constraint dufynd_resource_canonical_check
 check(public.dufynd_valid_resource_scope(resource_scope));

create or replace function public.reconcile_dufynd_supervisor_v2()
returns jsonb language plpgsql security invoker set search_path=public as $$
declare t record; legacy jsonb; findings jsonb := '[]'; reason text; destination text;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 perform set_config('dufynd.worker_write','supervisor',true);
 select value into legacy from public.dufynd_master_status where key='continuity.tech_lease' for update;
 if legacy->>'status'='active' and (nullif(legacy->>'released_at','') is not null
   or coalesce(public.dufynd_parse_timestamp(legacy->>'expires_at'),'-infinity')<=now()) then
   update public.dufynd_master_status set value=legacy||jsonb_build_object(
     'status',case when nullif(legacy->>'released_at','') is not null then 'released' else 'expired' end,
     'reconciled_at',now(),'reconciliation_reason','inactive_lease'), last_verified_at=now()
   where key='continuity.tech_lease';
   findings:=findings||jsonb_build_array(jsonb_build_object('kind','legacy_lease_repaired','owner',legacy->>'owner'));
 end if;
 for t in select * from public.dufynd_autonomy_tasks where worker_state in ('claimed','working','verifying','stale') for update loop
   reason:=case when t.status='done' then 'verified_terminal_state'
     when t.released_at is not null then 'released_lease'
     when t.lease_expires_at is null or t.lease_expires_at<=now() then 'lease_expired'
     when t.heartbeat_at is null or t.heartbeat_at<now()-interval '180 seconds' then 'heartbeat_stale'
     when t.last_progress_at is null or t.last_progress_at<now()-interval '600 seconds' then 'progress_stalled'
     else null end;
   if reason is null then continue; end if;
   -- Unknown paid outcomes are quarantined. Never infer done from model prose.
   destination:=case when t.status='done' then 'done'
     when t.provider_cost_unknown or t.budget_class='model' then 'blocked'
     when t.retry_count>=2 then 'failed_terminal' else 'failed_retryable' end;
   update public.dufynd_autonomy_tasks set worker_state=destination,
     status=case when destination='done' then 'done' when destination='failed_retryable' then 'ready' else 'blocked' end,
     blocked_reason=reason, released_at=coalesce(released_at,now()), lease_expires_at=now(),
     retry_count=retry_count+case when destination='failed_retryable' then 1 else 0 end,
     evidence=right(coalesce(evidence,'')||E'\nSupervisor V2 recovery: '||reason||' -> '||destination,12000)
   where task_id=t.task_id;
   findings:=findings||jsonb_build_array(jsonb_build_object('task_id',t.task_id,'kind','stale_recovery','reason',reason,'destination',destination));
 end loop;
 -- Dependencies are exact task IDs. Malformed dependency data is not runnable.
 update public.dufynd_autonomy_tasks q set status='ready',worker_state='ready',blocked_reason=null
 where q.worker_state='queued' and q.status='planned' and not q.requires_human_approval
 and jsonb_typeof(q.dependencies)='array' and not exists (
   select 1 from jsonb_array_elements_text(q.dependencies) d
   where not exists(select 1 from public.dufynd_autonomy_tasks x where x.task_id=d and x.status='done'));
 update public.dufynd_autonomy_tasks set worker_state='queued', blocked_reason=case
   when not coalesce((public.get_dufynd_jarvis_budget_status('jarvis_activation_pilot_001')->>'can_run')::boolean,false)
   then 'budget_exhausted' else 'unbounded_provider_cost' end
 where status='ready' and budget_class='model' and (released_at is not null or lease_token is null);
 findings:=findings||jsonb_build_array(jsonb_build_object('kind','health_summary',
   'ready_without_owner',(select count(*) from public.dufynd_autonomy_tasks where status='ready' and (released_at is not null or lease_token is null)),
   'budget_paused',(select count(*) from public.dufynd_autonomy_tasks where blocked_reason in ('budget_exhausted','unbounded_provider_cost')),
   'unclassified_human_gates',(select count(*) from public.dufynd_autonomy_tasks where status='waiting_human_input' and blocked_reason is null),
   'inbox_pending',(select count(*) from public.dufynd_jarvis_inbox where status='pending'),
   'inbox_failed',(select count(*) from public.dufynd_jarvis_inbox where status='failed'),
   'inbox_stale',(select count(*) from public.dufynd_jarvis_inbox where status='processing' and claimed_at<now()-interval '600 seconds')));
 insert into public.dufynd_master_status(key,category,value,priority,last_verified_at)
 values('jarvis.supervisor_v2.health','jarvis',jsonb_build_object('version',2,'checked_at',now(),'findings',findings),100,now())
 on conflict(key) do update set value=excluded.value,last_verified_at=excluded.last_verified_at;
 perform set_config('dufynd.worker_write','',true);
 return jsonb_build_object('version',2,'checked_at',now(),'findings',findings);
end $$;

create or replace function public.claim_dufynd_worker_v2(p_task_id text,p_owner text,p_token uuid)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare t public.dufynd_autonomy_tasks; legacy jsonb;
begin
 perform public.reconcile_dufynd_supervisor_v2();
 select * into t from public.dufynd_autonomy_tasks where task_id=p_task_id for update;
 if not found or t.status<>'ready' or t.requires_human_approval or nullif(p_owner,'') is null or p_token is null then return null; end if;
 if t.released_at is null and t.lease_expires_at>now() then return null; end if;
 if jsonb_typeof(t.dependencies)<>'array' or exists (select 1 from jsonb_array_elements_text(t.dependencies) d
   where not exists(select 1 from public.dufynd_autonomy_tasks x where x.task_id=d and x.status='done')) then return null; end if;
 if exists(select 1 from public.dufynd_autonomy_tasks x where x.task_id<>t.task_id
   and x.released_at is null and x.lease_expires_at>now() and x.worker_state in ('claimed','working','verifying')
   and public.dufynd_resources_conflict(t.resource_scope,x.resource_scope)) then return null; end if;
 select value into legacy from public.dufynd_master_status where key='continuity.tech_lease';
 if legacy->>'status'='active' and nullif(legacy->>'released_at','') is null
   and public.dufynd_parse_timestamp(legacy->>'expires_at')>now()
   and (t.domain='engineering' or public.dufynd_resources_conflict(t.resource_scope,'["repo:*"]')) then return null; end if;
 perform set_config('dufynd.worker_write',p_token::text,true);
 update public.dufynd_autonomy_tasks set status='in_progress',worker_state='claimed',worker_owner=p_owner,
   lease_token=p_token, started_at=now(),heartbeat_at=now(),last_progress_at=now(),
   lease_expires_at=now()+interval '180 seconds',released_at=null,blocked_reason=null,
   expected_next_checkpoint='worker_result_or_deterministic_verification'
 where task_id=p_task_id returning * into t;
 perform set_config('dufynd.worker_write','',true);
 return to_jsonb(t);
end $$;

create or replace function public.update_dufynd_worker_v2(p_task_id text,p_token uuid,p_state text,p_evidence text default null,p_reason text default null)
returns boolean language plpgsql security invoker set search_path=public as $$
declare t public.dufynd_autonomy_tasks; destination text:=p_state;
begin
 select * into t from public.dufynd_autonomy_tasks where task_id=p_task_id for update;
 if not found or t.lease_token is distinct from p_token or p_token is null or t.released_at is not null
   or t.lease_expires_at<=now() or t.worker_state not in ('claimed','working','verifying') then return false; end if;
 perform set_config('dufynd.worker_write',p_token::text,true);
 if p_state='heartbeat' then
   -- Heartbeats never advance progress or revive a stalled worker.
   if t.last_progress_at is null or t.last_progress_at<now()-interval '600 seconds' then
     perform set_config('dufynd.worker_write','',true); return false;
   end if;
   update public.dufynd_autonomy_tasks set heartbeat_at=now(),lease_expires_at=now()+interval '180 seconds' where task_id=p_task_id;
   perform set_config('dufynd.worker_write','',true);
   return true;
 end if;
 if destination not in ('working','verifying','done','queued','waiting_external','waiting_human_input','blocked','failed_retryable','failed_terminal') then raise exception 'invalid worker state'; end if;
 if destination='waiting_human_input' and coalesce(p_reason,'') not in ('owner_decision','spend_approval','publication_approval','contract_approval') then
   destination:='queued'; p_reason:='unclassified_human_gate';
 end if;
 if destination='waiting_external' and coalesce(p_reason,'') not in ('external_dependency','verification_pending') then raise exception 'external dependency reason required'; end if;
 if destination='done' and (t.worker_state<>'verifying' or nullif(p_evidence,'') is null) then raise exception 'verification evidence required'; end if;
 if destination='failed_retryable' and (t.provider_cost_unknown or t.retry_count>=2) then destination:='blocked'; end if;
 update public.dufynd_autonomy_tasks set worker_state=destination,
   status=case when destination in ('working','verifying') then 'in_progress'
     when destination in ('queued','failed_retryable') then 'ready'
     when destination='failed_terminal' then 'blocked' else destination end,
   heartbeat_at=now(),last_progress_at=case when nullif(p_evidence,'') is not null and p_evidence is distinct from t.evidence then now() else last_progress_at end,
   evidence=coalesce(p_evidence,evidence),blocked_reason=p_reason,
   expected_next_checkpoint=case when destination='done' then null
     when p_reason='verification_pending' then 'deterministic_verification'
     when destination='queued' then 'next_safe_worker_or_budget_reopen'
     when destination='waiting_human_input' then 'typed_owner_decision'
     when destination='waiting_external' then 'external_dependency_resolution'
     else expected_next_checkpoint end,
   lease_expires_at=case when destination in ('working','verifying') then now()+interval '180 seconds' else now() end,
   released_at=case when destination in ('working','verifying') then null else now() end,
   retry_count=retry_count+case when destination='failed_retryable' then 1 else 0 end
 where task_id=p_task_id;
 perform set_config('dufynd.worker_write','',true);
 return true;
end $$;

create or replace function public.guard_dufynd_worker_v2()
returns trigger language plpgsql security invoker set search_path=public as $$
begin
 if old.lease_token is not null and old.released_at is null
   and coalesce(current_setting('dufynd.worker_write',true),'') not in (old.lease_token::text,'supervisor') then
   if (to_jsonb(new)-'updated_at') is distinct from (to_jsonb(old)-'updated_at') then raise exception 'active worker lease requires fenced RPC'; end if;
 end if;
 if new.status is distinct from old.status and new.worker_state=old.worker_state
   and (old.released_at is not null or old.lease_token is null) then
   new.worker_state:=case when new.status in ('done','ready','waiting_external','waiting_human_input','blocked') then new.status
     when new.status='in_progress' then 'stale' else 'queued' end;
 end if;
 return new;
end $$;
create trigger dufynd_worker_v2_guard before update on public.dufynd_autonomy_tasks
for each row execute function public.guard_dufynd_worker_v2();

create or replace function public.normalize_dufynd_legacy_lease_v2()
returns trigger language plpgsql security invoker set search_path=public as $$
begin
 if new.key='continuity.tech_lease' and new.value->>'status'='active' then
   if nullif(new.value->>'released_at','') is not null then
     new.value:=new.value||'{"status":"released","reconciliation_reason":"released_at_present"}'::jsonb;
   elsif coalesce(public.dufynd_parse_timestamp(new.value->>'expires_at'),'-infinity')<=now() then
     new.value:=new.value||'{"status":"expired","reconciliation_reason":"ttl_expired_or_invalid"}'::jsonb;
   end if;
 end if;
 return new;
end $$;
create trigger dufynd_legacy_lease_v2_normalize before insert or update on public.dufynd_master_status
for each row execute function public.normalize_dufynd_legacy_lease_v2();

-- These internal operations must never be callable by public clients.
revoke all on function public.dufynd_parse_timestamp(text), public.dufynd_resources_conflict(jsonb,jsonb),
 public.reconcile_dufynd_supervisor_v2(), public.claim_dufynd_worker_v2(text,text,uuid),
 public.update_dufynd_worker_v2(text,uuid,text,text,text) from public,anon,authenticated;
grant execute on function public.dufynd_parse_timestamp(text), public.dufynd_resources_conflict(jsonb,jsonb),
 public.reconcile_dufynd_supervisor_v2(), public.claim_dufynd_worker_v2(text,text,uuid),
 public.update_dufynd_worker_v2(text,uuid,text,text,text) to service_role;
revoke all on function public.guard_dufynd_worker_v2(), public.normalize_dufynd_legacy_lease_v2() from public,anon,authenticated;
grant execute on function public.guard_dufynd_worker_v2(), public.normalize_dufynd_legacy_lease_v2() to service_role;
revoke all on function public.dufynd_valid_resource_scope(jsonb) from public,anon,authenticated;
grant execute on function public.dufynd_valid_resource_scope(jsonb) to service_role;

-- No model and no paid runner: watchdog survives chat/workflow termination.
create extension if not exists pg_cron with schema pg_catalog;
select cron.schedule('dufynd-supervisor-v2-health','*/2 * * * *','select public.reconcile_dufynd_supervisor_v2();');
