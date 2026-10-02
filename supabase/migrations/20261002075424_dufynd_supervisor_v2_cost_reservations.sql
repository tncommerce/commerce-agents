-- Phase 2A: exact decimal accounting and serialized per-budget admission.
-- Existing budgets are deliberately NOT enabled. No old approval is reused.
alter table public.dufynd_jarvis_budget_windows
 add column reservation_enabled boolean not null default false,
 add column reservation_dry_run boolean not null default false;
create table public.dufynd_provider_contracts (
 contract_id text primary key,
 model text not null,
 max_call_usd numeric not null check(max_call_usd > 0 and max_call_usd < 'Infinity'::numeric),
 dry_run boolean not null default true,
 enabled boolean not null default false,
 evidence jsonb not null,
 expires_at timestamptz not null
);
create table public.dufynd_budget_reservations (
 reservation_id uuid primary key default gen_random_uuid(),
 budget_id text not null references public.dufynd_jarvis_budget_windows(budget_id),
 task_id text not null references public.dufynd_autonomy_tasks(task_id),
 worker_owner text not null,
 lease_token uuid not null,
 idempotency_key text not null check(length(idempotency_key) between 1 and 200),
 request_hash text not null check(length(request_hash)=64),
 contract_id text not null references public.dufynd_provider_contracts(contract_id),
 reserved_usd numeric not null check(reserved_usd > 0 and reserved_usd < 'Infinity'::numeric),
 actual_usd numeric check(actual_usd >= 0 and actual_usd <= reserved_usd),
 status text not null default 'reserved' check(status in ('reserved','dispatched','settled','released','charged_max')),
 created_at timestamptz not null default clock_timestamp(),
 expires_at timestamptz not null,
 dispatched_at timestamptz,
 settled_at timestamptz,
 evidence jsonb not null default '[]',
 unique(budget_id,idempotency_key)
);
create index dufynd_reservation_expiry on public.dufynd_budget_reservations(expires_at) where status in ('reserved','dispatched');
alter table public.dufynd_provider_contracts enable row level security;
alter table public.dufynd_budget_reservations enable row level security;
revoke all on public.dufynd_provider_contracts,public.dufynd_budget_reservations from public,anon,authenticated;
grant all on public.dufynd_provider_contracts,public.dufynd_budget_reservations to service_role;

create or replace function public.get_dufynd_jarvis_budget_status(p_budget_id text)
returns jsonb language sql stable security invoker set search_path=public as $$
with b as (select * from public.dufynd_jarvis_budget_windows where budget_id=p_budget_id),
legacy as (
 select count(distinct r.id) as runs,
 coalesce(sum(case when d.value->>'budget_id'=p_budget_id and (d.value->>'cost_usd') ~ '^[0-9]+([.][0-9]+)?$'
 then (d.value->>'cost_usd')::numeric else 0 end),0) as spent,
 coalesce(bool_or(d.value->>'budget_id'=p_budget_id and (coalesce(d.value->>'provider_cost_unknown','false')='true'
 or not coalesce((d.value->>'cost_usd') ~ '^[0-9]+([.][0-9]+)?$',false))),false) as unknown
 from public.dufynd_agent_runs r cross join lateral jsonb_array_elements(coalesce(r.decisions,'[]')) d(value)
 where r.agent_name='jarvis' and d.value->>'budget_id'=p_budget_id
 -- Ledger is authoritative for tagged bounded calls; never double count run audit.
 and not (d.value ? 'reservation_id')
), ledger as (
 select coalesce(sum(actual_usd) filter(where status in ('settled','charged_max')),0) as spent,
 coalesce(sum(reserved_usd) filter(where status in ('reserved','dispatched')),0) as reserved,
 count(*) filter(where status <> 'released') as runs
 from public.dufynd_budget_reservations where budget_id=p_budget_id
)
select case when b.budget_id is null then jsonb_build_object('budget_id',p_budget_id,'state','missing','can_run',false)
 else jsonb_build_object('budget_id',b.budget_id,'title',b.title,'status',b.status,'model',b.model,
 'cap_usd',b.cap_usd,'max_runs',b.max_runs,'runs',legacy.runs+ledger.runs,
 'spent_usd',legacy.spent+ledger.spent,'reserved_unsettled_usd',ledger.reserved,
 'remaining_usd',greatest(b.cap_usd-legacy.spent-ledger.spent-ledger.reserved,0),
 'remaining_runs',greatest(b.max_runs-legacy.runs-ledger.runs,0),'provider_cost_unknown',legacy.unknown,
 'reservation_enabled',b.reservation_enabled,'reservation_dry_run',b.reservation_dry_run,
 'can_run',b.status='active' and not legacy.unknown and legacy.spent+ledger.spent+ledger.reserved<b.cap_usd
 and legacy.runs+ledger.runs<b.max_runs) end
from b full join legacy on true cross join ledger limit 1;
$$;

create function public.reserve_dufynd_model_call(p_budget_id text,p_task_id text,p_owner text,p_lease_token uuid,
 p_idempotency_key text,p_request_hash text,p_contract_id text,p_max_usd numeric,p_ttl_seconds integer default 180)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare b public.dufynd_jarvis_budget_windows; c public.dufynd_provider_contracts;
 r public.dufynd_budget_reservations; t public.dufynd_autonomy_tasks; s jsonb; approved jsonb;
begin
 -- Always budget -> reservation -> task lock order. A new statement after the
 -- row lock observes the preceding claimant's committed reservation at READ COMMITTED.
 select * into b from public.dufynd_jarvis_budget_windows where budget_id=p_budget_id for update;
 if not found then return jsonb_build_object('allowed',false,'reason','budget_missing'); end if;
 select * into r from public.dufynd_budget_reservations where budget_id=p_budget_id and idempotency_key=p_idempotency_key;
 if found then
   if r.task_id is distinct from p_task_id or r.worker_owner is distinct from p_owner or r.lease_token is distinct from p_lease_token
   or r.request_hash is distinct from p_request_hash or r.contract_id is distinct from p_contract_id or r.reserved_usd is distinct from p_max_usd
   then return jsonb_build_object('allowed',false,'reason','idempotency_conflict'); end if;
   return jsonb_build_object('allowed',r.status='reserved','reused',true,'reservation',to_jsonb(r));
 end if;
 select * into c from public.dufynd_provider_contracts where contract_id=p_contract_id;
 if not found or not c.enabled or c.expires_at<=clock_timestamp() or p_max_usd is null
 or p_max_usd<=0 or p_max_usd>'1000000'::numeric or p_max_usd='NaN'::numeric or p_max_usd<c.max_call_usd
 then return jsonb_build_object('allowed',false,'reason','unbounded_provider_cost'); end if;
 if not b.reservation_enabled or b.reservation_dry_run<>c.dry_run or b.model is distinct from c.model
 then return jsonb_build_object('allowed',false,'reason','provider_not_authorized'); end if;
 -- Paid authorization requires a NEW Phase-2-specific approval and a certified
 -- contract. Migration creates neither. Fake contracts cannot authorize payment.
 if not c.dry_run then
   select decision into approved from public.dufynd_human_decisions where decision_id=b.approved_decision_id and status='approved';
   if approved is null or approved->>'approved'<>'true' or approved->>'scope'<>'supervisor_v2_bounded_canary'
   or approved->>'budget_id' is distinct from b.budget_id or approved->>'contract_id' is distinct from c.contract_id
   or not coalesce((approved->>'cap_usd') ~ '^[0-9]+([.][0-9]+)?$',false)
   or not coalesce((approved->>'per_call_cap_usd') ~ '^[0-9]+([.][0-9]+)?$',false)
   or not coalesce((approved->>'max_runs') ~ '^[0-9]+$',false)
   then return jsonb_build_object('allowed',false,'reason','new_budget_approval_required'); end if;
   if b.cap_usd>(approved->>'cap_usd')::numeric or p_max_usd>(approved->>'per_call_cap_usd')::numeric
   or b.max_runs>(approved->>'max_runs')::numeric then return jsonb_build_object('allowed',false,'reason','approval_limit'); end if;
 end if;
 select * into t from public.dufynd_autonomy_tasks where task_id=p_task_id for update;
 if not found or t.worker_owner is distinct from p_owner or t.lease_token is distinct from p_lease_token
 or t.released_at is not null or coalesce(t.lease_expires_at,'-infinity')<=clock_timestamp()
 or t.worker_state not in ('claimed','working') then return jsonb_build_object('allowed',false,'reason','worker_lease_lost'); end if;
 s:=public.get_dufynd_jarvis_budget_status(p_budget_id);
 if b.status<>'active' or coalesce((s->>'provider_cost_unknown')::boolean,true)
 or (s->>'remaining_runs')::integer<1 or b.cap_usd-(s->>'spent_usd')::numeric-(s->>'reserved_unsettled_usd')::numeric-p_max_usd<0
 then return jsonb_build_object('allowed',false,'reason','budget_exhausted'); end if;
 if p_ttl_seconds is null or p_ttl_seconds not between 1 and 600 then return jsonb_build_object('allowed',false,'reason','invalid_ttl'); end if;
 insert into public.dufynd_budget_reservations(budget_id,task_id,worker_owner,lease_token,idempotency_key,request_hash,contract_id,reserved_usd,expires_at,evidence)
 values(p_budget_id,p_task_id,p_owner,p_lease_token,p_idempotency_key,p_request_hash,p_contract_id,p_max_usd,
 clock_timestamp()+make_interval(secs=>p_ttl_seconds),jsonb_build_array(jsonb_build_object('event','reserved','at',clock_timestamp(),'bound_contract',c.evidence))) returning * into r;
 return jsonb_build_object('allowed',true,'reused',false,'reservation',to_jsonb(r));
end $$;

create function public.dispatch_dufynd_model_call(p_reservation_id uuid,p_lease_token uuid)
returns boolean language plpgsql security invoker set search_path=public as $$
declare r public.dufynd_budget_reservations; b public.dufynd_jarvis_budget_windows; t public.dufynd_autonomy_tasks;
begin
 select * into r from public.dufynd_budget_reservations where reservation_id=p_reservation_id;
 if not found then return false; end if;
 select * into b from public.dufynd_jarvis_budget_windows where budget_id=r.budget_id for update;
 select * into r from public.dufynd_budget_reservations where reservation_id=p_reservation_id for update;
 select * into t from public.dufynd_autonomy_tasks where task_id=r.task_id for update;
 if r.status<>'reserved' or r.expires_at<=clock_timestamp() or r.lease_token is distinct from p_lease_token
 or t.lease_token is distinct from p_lease_token or t.released_at is not null or coalesce(t.lease_expires_at,'-infinity')<=clock_timestamp()
 or not b.reservation_enabled or b.status<>'active'
 or not exists(select 1 from public.dufynd_provider_contracts c where c.contract_id=r.contract_id and c.enabled and c.expires_at>clock_timestamp())
 then return false; end if;
 update public.dufynd_budget_reservations set status='dispatched',dispatched_at=clock_timestamp(),
 evidence=evidence||jsonb_build_array(jsonb_build_object('event','dispatched','at',clock_timestamp())) where reservation_id=p_reservation_id;
 return true;
end $$;

create function public.settle_dufynd_model_call(p_reservation_id uuid,p_lease_token uuid,p_actual_usd numeric,p_evidence jsonb)
returns boolean language plpgsql security invoker set search_path=public as $$
declare r public.dufynd_budget_reservations;
begin
 select * into r from public.dufynd_budget_reservations where reservation_id=p_reservation_id;
 if not found then return false; end if;
 perform 1 from public.dufynd_jarvis_budget_windows where budget_id=r.budget_id for update;
 select * into r from public.dufynd_budget_reservations where reservation_id=p_reservation_id for update;
 if r.lease_token is distinct from p_lease_token or p_actual_usd is null or p_actual_usd<0 or p_actual_usd>r.reserved_usd
 or p_actual_usd='NaN'::numeric or p_evidence is null or p_evidence='{}'::jsonb then return false; end if;
 if r.status='settled' then return r.actual_usd=p_actual_usd; end if;
 -- Late verified usage can replace a conservative max charge; never reopen dispatch.
 if r.status not in ('dispatched','charged_max') then return false; end if;
 update public.dufynd_budget_reservations set status='settled',actual_usd=p_actual_usd,settled_at=clock_timestamp(),
 evidence=evidence||jsonb_build_array(jsonb_build_object('event','settled','at',clock_timestamp(),'usage',p_evidence,'actual_usd',p_actual_usd)) where reservation_id=p_reservation_id;
 return true;
end $$;

create function public.reconcile_dufynd_budget_reservations()
returns jsonb language plpgsql security invoker set search_path=public as $$
declare b text; n integer:=0; changed integer;
begin
 for b in select distinct budget_id from public.dufynd_budget_reservations where status in ('reserved','dispatched') and expires_at<=clock_timestamp() order by budget_id loop
   perform 1 from public.dufynd_jarvis_budget_windows where budget_id=b for update;
   update public.dufynd_budget_reservations set
   status=case when status='reserved' then 'released' else 'charged_max' end,
   actual_usd=case when status='reserved' then 0 else reserved_usd end,settled_at=clock_timestamp(),
   evidence=evidence||jsonb_build_array(jsonb_build_object('event','ttl_reconciled','at',clock_timestamp(),'prior_status',status,'rule','undispatched_release_otherwise_charge_max'))
   where budget_id=b and status in ('reserved','dispatched') and expires_at<=clock_timestamp();
   get diagnostics changed=row_count; n:=n+changed;
 end loop;
 return jsonb_build_object('reconciled',n,'checked_at',clock_timestamp());
end $$;
-- Preserve Phase-1 worker reconciliation; extend the same autonomous watchdog.
alter function public.reconcile_dufynd_supervisor_v2() rename to reconcile_dufynd_supervisor_v2_workers;
create function public.reconcile_dufynd_supervisor_v2()
returns jsonb language plpgsql security invoker set search_path=public as $$
declare budgets jsonb; workers jsonb;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 budgets:=public.reconcile_dufynd_budget_reservations();
 workers:=public.reconcile_dufynd_supervisor_v2_workers();
 update public.dufynd_master_status set value=value||jsonb_build_object('budget_reservations',budgets)
 where key='jarvis.supervisor_v2.health';
 return workers||jsonb_build_object('budget_reservations',budgets);
end $$;
revoke all on function public.reserve_dufynd_model_call(text,text,text,uuid,text,text,text,numeric,integer),
 public.dispatch_dufynd_model_call(uuid,uuid),public.settle_dufynd_model_call(uuid,uuid,numeric,jsonb),
 public.reconcile_dufynd_budget_reservations(),public.reconcile_dufynd_supervisor_v2(),public.get_dufynd_jarvis_budget_status(text) from public,anon,authenticated;
grant execute on function public.reserve_dufynd_model_call(text,text,text,uuid,text,text,text,numeric,integer),
 public.dispatch_dufynd_model_call(uuid,uuid),public.settle_dufynd_model_call(uuid,uuid,numeric,jsonb),
 public.reconcile_dufynd_budget_reservations(),public.reconcile_dufynd_supervisor_v2(),public.get_dufynd_jarvis_budget_status(text) to service_role;

-- Cap reductions cannot invalidate existing reservations. Historical overrun
-- budgets remain untouched; any subsequent reduction fails closed.
create function public.guard_dufynd_reserved_cap()
returns trigger language plpgsql security invoker set search_path=public as $$
declare s jsonb;
begin
 if new.cap_usd is distinct from old.cap_usd then
   s:=public.get_dufynd_jarvis_budget_status(old.budget_id);
   if new.cap_usd<(s->>'spent_usd')::numeric+(s->>'reserved_unsettled_usd')::numeric then
     raise exception 'cap cannot invalidate committed costs or reservations';
   end if;
 end if;
 return new;
end $$;
create trigger dufynd_reserved_cap_guard before update on public.dufynd_jarvis_budget_windows
for each row execute function public.guard_dufynd_reserved_cap();
revoke all on function public.guard_dufynd_reserved_cap() from public,anon,authenticated;
grant execute on function public.guard_dufynd_reserved_cap() to service_role;
