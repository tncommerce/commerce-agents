-- Revalidate authorization under the existing budget/reservation/task lock order.
-- Creates no budget, approval or provider contract and enables no paid transport.
create or replace function public.reserve_dufynd_model_call(p_budget_id text,p_task_id text,p_owner text,p_lease_token uuid,
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
   if approved is null or approved->'approved' is distinct from 'true'::jsonb or approved->>'scope' is distinct from 'supervisor_v2_bounded_canary'
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

create or replace function public.dispatch_dufynd_model_call(p_reservation_id uuid,p_lease_token uuid)
returns boolean language plpgsql security invoker set search_path=public as $$
declare
 r public.dufynd_budget_reservations;
 b public.dufynd_jarvis_budget_windows;
 t public.dufynd_autonomy_tasks;
 c public.dufynd_provider_contracts;
 approved jsonb;
 s jsonb;
begin
 select * into r from public.dufynd_budget_reservations where reservation_id=p_reservation_id;
 if not found then return false; end if;
 select * into b from public.dufynd_jarvis_budget_windows where budget_id=r.budget_id for update;
 if not found then return false; end if;
 select * into r from public.dufynd_budget_reservations where reservation_id=p_reservation_id for update;
 select * into t from public.dufynd_autonomy_tasks where task_id=r.task_id for update;
 if not found then return false; end if;
 if r.status is distinct from 'reserved' or r.expires_at<=clock_timestamp()
 or r.lease_token is distinct from p_lease_token or t.lease_token is distinct from p_lease_token
 or t.worker_owner is distinct from r.worker_owner or t.released_at is not null
 or coalesce(t.lease_expires_at,'-infinity')<=clock_timestamp()
 or coalesce(t.worker_state,'') not in ('claimed','working')
 or b.reservation_enabled is not true or b.status is distinct from 'active'
 then return false; end if;
 select * into c from public.dufynd_provider_contracts where contract_id=r.contract_id for share;
 if not found then return false; end if;
 if c.enabled is not true or c.expires_at<=clock_timestamp()
 or b.model is distinct from c.model or b.reservation_dry_run is distinct from c.dry_run
 or r.reserved_usd<c.max_call_usd
 or r.evidence->0->'bound_contract' is distinct from c.evidence
 then return false; end if;
 if not c.dry_run then
   select decision into approved from public.dufynd_human_decisions
   where decision_id=b.approved_decision_id and status='approved' for share;
   if approved is null or approved->'approved' is distinct from 'true'::jsonb
   or approved->>'scope' is distinct from 'supervisor_v2_bounded_canary'
   or approved->>'budget_id' is distinct from b.budget_id
   or approved->>'contract_id' is distinct from c.contract_id
   or not coalesce((approved->>'cap_usd') ~ '^[0-9]+([.][0-9]+)?$',false)
   or not coalesce((approved->>'per_call_cap_usd') ~ '^[0-9]+([.][0-9]+)?$',false)
   or not coalesce((approved->>'max_runs') ~ '^[0-9]+$',false)
   then return false; end if;
   if b.cap_usd>(approved->>'cap_usd')::numeric
   or r.reserved_usd>(approved->>'per_call_cap_usd')::numeric
   or b.max_runs>(approved->>'max_runs')::numeric then return false; end if;
 end if;
 s:=public.get_dufynd_jarvis_budget_status(b.budget_id);
 -- The current reservation already counts as a run: equality must be permitted.
 if coalesce((s->>'provider_cost_unknown')::boolean,true)
 or (s->>'runs')::numeric>b.max_runs
 or (s->>'spent_usd')::numeric+(s->>'reserved_unsettled_usd')::numeric>b.cap_usd
 then return false; end if;
 update public.dufynd_budget_reservations set status='dispatched',dispatched_at=clock_timestamp(),
 evidence=evidence||jsonb_build_array(jsonb_build_object('event','dispatched','at',clock_timestamp(),
 'authorization_revalidated',true)) where reservation_id=p_reservation_id;
 return true;
end $$;
revoke all on function public.dispatch_dufynd_model_call(uuid,uuid),
 public.reserve_dufynd_model_call(text,text,text,uuid,text,text,text,numeric,integer) from public,anon,authenticated;
grant execute on function public.dispatch_dufynd_model_call(uuid,uuid),
 public.reserve_dufynd_model_call(text,text,text,uuid,text,text,text,numeric,integer) to service_role;
