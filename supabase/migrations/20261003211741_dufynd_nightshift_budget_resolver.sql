-- Pricing registration is not a budget approval. No budget/window/decision is created.
alter table public.dufynd_jarvis_budget_windows add column if not exists provider text;
alter table public.dufynd_jarvis_budget_windows add column if not exists started_at timestamptz default now();
alter table public.dufynd_jarvis_budget_windows add column if not exists ended_at timestamptz;
alter table public.dufynd_budget_reservations add column if not exists provider_receipt_id text;
create unique index if not exists dufynd_unique_provider_receipt on public.dufynd_budget_reservations(provider_receipt_id) where provider_receipt_id is not null;
-- Actual provider billing must remain visible even if the estimate margin fails.
do $$ declare constraint_name text; begin
 for constraint_name in select conname from pg_constraint where conrelid='public.dufynd_budget_reservations'::regclass
 and contype='c' and pg_get_constraintdef(oid) like '%actual_usd%reserved_usd%' loop
 execute format('alter table public.dufynd_budget_reservations drop constraint %I',constraint_name);
 end loop;
end $$;
alter table public.dufynd_budget_reservations add constraint dufynd_actual_cost_finite check(actual_usd is null or (actual_usd>=0 and actual_usd<'Infinity'::numeric));
insert into public.dufynd_provider_contracts(contract_id,model,max_call_usd,dry_run,enabled,evidence,expires_at)
values('anthropic-sonnet5-counted-margin-v1','claude-sonnet-5',0.036864,false,true,'{"contract_id": "anthropic-sonnet5-counted-margin-v1", "provider": "anthropic", "model": "claude-sonnet-5", "verified_at": "2026-10-03T21:21:37.633014+00:00", "expires_at": "2026-10-04T21:21:37.633014+00:00", "sources": ["https://platform.claude.com/docs/en/about-claude/pricing", "https://platform.claude.com/docs/en/models/sonnet-5/overview"], "rates_usd_per_million": {"input": "2", "output": "10", "cache_read": "0.20", "cache_write_5m": "2.50", "cache_write_1h": "4"}, "policy": "estimate_margin_v1", "estimate_is_exact": false, "margin_multiplier": "1.25", "padding_tokens": 128, "max_input_tokens": 8192, "max_output_tokens": 2048, "max_request_usd": "0.036864", "pricing_scope": "standard_only/global/no_cache/no_tools; USD token charges before taxes", "pricing_digest": "97d63180179aa6d6a2c5b8d6c91aa20052ad116cfa4fd41c5fc9ee6609d30266", "input_bound_certified": false, "pricing_verified": true, "scope": "standard_only/global/no_cache/no_tools"}'::jsonb,'2026-10-04T21:21:37.633014+00:00');
create function public.resolve_dufynd_nightshift_budget(p_contract_id text,p_pricing_digest text,p_reserved_budget_id text default null)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare c public.dufynd_provider_contracts; candidate record; chosen jsonb; n integer:=0; s jsonb;
begin
 select * into c from public.dufynd_provider_contracts where contract_id=p_contract_id;
 if not found or c.enabled is not true or c.dry_run or c.expires_at<=clock_timestamp()
 or c.model<>'claude-sonnet-5' or c.evidence->>'provider' is distinct from 'anthropic'
 or c.evidence->>'pricing_digest' is distinct from p_pricing_digest
 or c.evidence->>'policy' is distinct from 'estimate_margin_v1'
 then return jsonb_build_object('allowed',false,'reason','provider_contract_unverified_or_expired'); end if;
 for candidate in select b.*,d.decision approval from public.dufynd_jarvis_budget_windows b
 join public.dufynd_human_decisions d on d.decision_id=b.approved_decision_id
 where b.provider='anthropic' and b.model=c.model and b.status='active'
 and b.started_at<=clock_timestamp() and (b.ended_at is null or b.ended_at>clock_timestamp())
 and b.reservation_enabled and not b.reservation_dry_run and d.status='approved'
 and d.decision->'approved'='true'::jsonb
 and d.decision->>'scope'='supervisor_v2_bounded_canary'
 and d.decision->>'provider'='anthropic' and d.decision->>'model'=c.model
 and d.decision->>'cost_policy'='estimate_margin_v1'
 and d.decision->'accept_estimate_margin'='true'::jsonb
 and d.decision->>'budget_id'=b.budget_id and d.decision->>'contract_id'=c.contract_id
 and b.cap_usd<=case when d.decision->>'cap_usd' ~ '^[0-9]+([.][0-9]+)?$' then (d.decision->>'cap_usd')::numeric end
 and b.max_runs<=case when d.decision->>'max_runs' ~ '^[0-9]+$' then (d.decision->>'max_runs')::numeric end
 and c.max_call_usd<=case when d.decision->>'per_call_cap_usd' ~ '^[0-9]+([.][0-9]+)?$' then (d.decision->>'per_call_cap_usd')::numeric end
 loop
   -- Serialize paid outcomes: no subsequent request until every sent call has a receipt.
   if exists(select 1 from public.dufynd_budget_reservations r where r.budget_id=candidate.budget_id and r.status='dispatched') then continue; end if;
   s:=public.get_dufynd_jarvis_budget_status(candidate.budget_id);
   if (s->'can_run'='true'::jsonb and (s->>'remaining_usd')::numeric>=c.max_call_usd)
   or (candidate.budget_id=p_reserved_budget_id and s->'provider_cost_unknown'='false'::jsonb
       and (s->>'runs')::numeric<=candidate.max_runs
       and (s->>'spent_usd')::numeric+(s->>'reserved_unsettled_usd')::numeric<=candidate.cap_usd) then
     n:=n+1; chosen:=jsonb_build_object('allowed',true,'budget',s,'window',to_jsonb(candidate),'contract',to_jsonb(c));
   end if;
 end loop;
 if n<>1 then return jsonb_build_object('allowed',false,'reason',case when n=0 then 'no_usable_approved_budget' else 'ambiguous_active_budgets' end); end if;
 return chosen;
end $$;

create function public.dispatch_dufynd_counted_call(p_reservation_id uuid,p_lease_token uuid,p_proof jsonb)
returns boolean language plpgsql security invoker set search_path=public as $$
declare r public.dufynd_budget_reservations; resolved jsonb; estimated numeric; bounded numeric; output numeric; calculated numeric;
begin
 select * into r from public.dufynd_budget_reservations where reservation_id=p_reservation_id;
 if not found then return false; end if;
 perform 1 from public.dufynd_jarvis_budget_windows where budget_id=r.budget_id for update;
 select * into r from public.dufynd_budget_reservations where reservation_id=p_reservation_id for update;
 if p_proof->>'policy' is distinct from 'estimate_margin_v1'
 or p_proof->>'request_hash' is distinct from r.request_hash
 or p_proof->>'margin_multiplier' is distinct from '1.25'
 or p_proof->'padding_tokens' is distinct from '128'::jsonb
 or p_proof->'estimate_is_exact' is distinct from 'false'::jsonb
 or coalesce(p_proof->>'estimated_input_tokens','') !~ '^[0-9]+$'
 or coalesce(p_proof->>'input_bound_tokens','') !~ '^[0-9]+$'
 or coalesce(p_proof->>'max_output_tokens','') !~ '^[0-9]+$'
 or coalesce(p_proof->>'calculated_max_usd','') !~ '^[0-9]+([.][0-9]+)?$'
 then return false; end if;
 if public.dufynd_parse_timestamp(p_proof->>'counted_at') is null
 or public.dufynd_parse_timestamp(p_proof->>'counted_at')>clock_timestamp()
 or public.dufynd_parse_timestamp(p_proof->>'counted_at')<clock_timestamp()-interval '120 seconds' then return false; end if;
 estimated:=(p_proof->>'estimated_input_tokens')::numeric;
 bounded:=(p_proof->>'input_bound_tokens')::numeric; output:=(p_proof->>'max_output_tokens')::numeric;
 calculated:=bounded*0.000002+output*0.000010;
 if bounded<>ceil(estimated*1.25)+128 or bounded>8192 or output not between 1 and 2048
 or calculated<>(p_proof->>'calculated_max_usd')::numeric or calculated>r.reserved_usd
 then return false; end if;
 perform 1 from public.dufynd_autonomy_tasks where task_id=r.task_id for update;
 perform 1 from public.dufynd_provider_contracts where contract_id=r.contract_id for share;
 perform 1 from public.dufynd_human_decisions d join public.dufynd_jarvis_budget_windows b on b.approved_decision_id=d.decision_id where b.budget_id=r.budget_id for share of d;
 resolved:=public.resolve_dufynd_nightshift_budget(r.contract_id,p_proof->>'pricing_digest',r.budget_id);
 -- Resolver counts this already-held run. Dispatch must permit the last reservation.
 -- Resolve before reservation in Python; here use explicit current authorization plus direct dispatch.
 if resolved->'allowed' is distinct from 'true'::jsonb or resolved->'budget'->>'budget_id' is distinct from r.budget_id then return false; end if;
 if not exists(select 1 from public.dufynd_jarvis_budget_windows b
 join public.dufynd_human_decisions d on d.decision_id=b.approved_decision_id
 join public.dufynd_provider_contracts c on c.contract_id=r.contract_id
 where b.budget_id=r.budget_id and b.provider='anthropic' and b.started_at<=clock_timestamp()
 and (b.ended_at is null or b.ended_at>clock_timestamp()) and d.status='approved'
 and d.decision->>'provider'='anthropic' and d.decision->>'model'='claude-sonnet-5'
 and d.decision->>'cost_policy'='estimate_margin_v1' and d.decision->'accept_estimate_margin'='true'::jsonb
 and c.evidence->>'pricing_digest'=p_proof->>'pricing_digest'
 and c.evidence->>'policy'='estimate_margin_v1') then return false; end if;
 if public.dispatch_dufynd_model_call(p_reservation_id,p_lease_token) is not true then return false; end if;
 update public.dufynd_budget_reservations set evidence=evidence||jsonb_build_array(jsonb_build_object('event','pre_request_cost_guard','proof',p_proof)) where reservation_id=p_reservation_id;
 return true;
end $$;

create function public.settle_dufynd_counted_call(p_reservation_id uuid,p_lease_token uuid,p_actual_usd numeric,p_evidence jsonb,p_violation boolean)
returns boolean language plpgsql security invoker set search_path=public as $$
declare r public.dufynd_budget_reservations; actual numeric; receipt text; proof jsonb; violated boolean;
begin
 select * into r from public.dufynd_budget_reservations where reservation_id=p_reservation_id;
 if not found then return false; end if;
 perform 1 from public.dufynd_jarvis_budget_windows where budget_id=r.budget_id for update;
 select * into r from public.dufynd_budget_reservations where reservation_id=p_reservation_id for update;
 if r.contract_id<>'anthropic-sonnet5-counted-margin-v1' or r.lease_token is distinct from p_lease_token
 or p_evidence is null or p_evidence='{}'::jsonb or p_violation is null then return false; end if;
 if p_actual_usd is not null then
   if coalesce(p_evidence->'usage'->>'input_tokens','') !~ '^[0-9]+$'
   or coalesce(p_evidence->'usage'->>'output_tokens','') !~ '^[0-9]+$'
   or p_evidence->>'provider' is distinct from 'anthropic' or p_evidence->>'model' is distinct from 'claude-sonnet-5'
   or nullif(p_evidence->>'provider_request_id','') is null then return false; end if;
   actual:=(p_evidence->'usage'->>'input_tokens')::numeric*0.000002+(p_evidence->'usage'->>'output_tokens')::numeric*0.000010;
   if actual is distinct from p_actual_usd or actual<0 or actual>1000000 then return false; end if;
   receipt:='anthropic:'||(p_evidence->>'provider_request_id');
 else
   if p_violation is not true or p_evidence->'unknown_cost' is distinct from 'true'::jsonb then return false; end if;
   actual:=r.reserved_usd;
 end if;
 select entry->'proof' into proof from jsonb_array_elements(r.evidence) entry where entry->>'event'='pre_request_cost_guard' limit 1;
 if proof is null then return false; end if;
 violated:=p_violation or actual>r.reserved_usd or p_actual_usd is null
 or (p_evidence->'usage'->>'input_tokens')::numeric>(proof->>'input_bound_tokens')::numeric
 or (p_evidence->'usage'->>'output_tokens')::numeric>(proof->>'max_output_tokens')::numeric;
 if receipt is not null and exists(select 1 from public.dufynd_budget_reservations where provider_receipt_id=receipt and reservation_id<>r.reservation_id) then
 update public.dufynd_jarvis_budget_windows set status='paused' where budget_id=r.budget_id; return false; end if;
 if r.status='settled' then return r.actual_usd=actual and r.provider_receipt_id is not distinct from receipt; end if;
 if r.status not in ('dispatched','charged_max') then return false; end if;
 update public.dufynd_budget_reservations set status=case when p_actual_usd is null then 'charged_max' else 'settled' end,
 actual_usd=actual,provider_receipt_id=receipt,settled_at=clock_timestamp(),
 evidence=evidence||jsonb_build_array(jsonb_build_object('event','counted_reconciled','actual_usd',p_actual_usd,
 'accounted_usd',actual,'evidence',p_evidence)) where reservation_id=p_reservation_id;
 if violated then
   update public.dufynd_jarvis_budget_windows set status='paused' where budget_id=r.budget_id;
 end if;
 return true;
exception when unique_violation then return false;
end $$;

alter function public.reconcile_dufynd_budget_reservations() rename to reconcile_dufynd_budget_reservations_v1;
create function public.reconcile_dufynd_budget_reservations()
returns jsonb language plpgsql security invoker set search_path=public as $$
begin
 -- An ambiguous sent counted request may have exceeded its estimate. Never continue paid work.
 update public.dufynd_jarvis_budget_windows b set status='paused' where exists(
 select 1 from public.dufynd_budget_reservations r where r.budget_id=b.budget_id
 and r.contract_id='anthropic-sonnet5-counted-margin-v1' and r.status='dispatched' and r.expires_at<=clock_timestamp());
 return public.reconcile_dufynd_budget_reservations_v1();
end $$;
revoke all on function public.resolve_dufynd_nightshift_budget(text,text,text),public.dispatch_dufynd_counted_call(uuid,uuid,jsonb),
 public.settle_dufynd_counted_call(uuid,uuid,numeric,jsonb,boolean),public.reconcile_dufynd_budget_reservations() from public,anon,authenticated;
grant execute on function public.resolve_dufynd_nightshift_budget(text,text,text),public.dispatch_dufynd_counted_call(uuid,uuid,jsonb),
 public.settle_dufynd_counted_call(uuid,uuid,numeric,jsonb,boolean),public.reconcile_dufynd_budget_reservations() to service_role;
