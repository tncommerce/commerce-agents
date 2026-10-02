-- One exact, PR-reviewed merchant target. No catalog/offer/business mutation.
create table public.dufynd_purchase_verification_targets (
 offer_id text primary key, product_id text not null, canonical_identity jsonb not null,
 offer_contract jsonb not null, max_age_hours int not null default 72 check(max_age_hours=72),
 safety_window_hours int not null default 24 check(safety_window_hours between 1 and 48),
 enabled boolean not null default false, last_verified_at timestamptz not null,
 retry_after timestamptz, last_result jsonb, certification_due boolean not null default false
);
create table public.dufynd_purchase_verification_evidence (
 execution_id uuid primary key references public.dufynd_execution_runs(execution_id),
 offer_id text not null references public.dufynd_purchase_verification_targets(offer_id),
 observed_at timestamptz not null, decision text not null, report jsonb not null, report_hash text not null
);
alter table public.dufynd_purchase_verification_targets enable row level security;
alter table public.dufynd_purchase_verification_evidence enable row level security;
revoke all on public.dufynd_purchase_verification_targets,public.dufynd_purchase_verification_evidence from public,anon,authenticated;
grant all on public.dufynd_purchase_verification_targets,public.dufynd_purchase_verification_evidence to service_role;
alter table public.dufynd_execution_runs add column purchase_request_id bigint,
 add column purchase_shipping_request_id bigint, add column purchase_requested_at timestamptz;


insert into public.dufynd_purchase_verification_targets(offer_id,product_id,canonical_identity,offer_contract,last_verified_at) values('perfumetrader-rabanne-1-million-edt-100','SC-RABANNE-1-MILLION-EDT-100','{"brand": "Rabanne", "name": "1 Million", "concentration": "Eau de Toilette", "volume_ml": 100, "gtin": "3349666007921", "merchant_product_id": "16978322", "merchant_variant": "standard spray, non-refill selected by exact GTIN"}'::jsonb,'{"offer_id": "perfumetrader-rabanne-1-million-edt-100", "product_id": "SC-RABANNE-1-MILLION-EDT-100", "merchant_id": "perfumetrader", "merchant_name": "Perfumetrader", "merchant_product_id": "16978322", "price": 71.9, "currency": "EUR", "shipping_cost": 4.99, "shipping_label": "4,99 € DHL Standardversand innerhalb Deutschlands", "in_stock": true, "variant_label": "100 ml · Eau de Toilette", "product_url": "https://www.perfumetrader.de/de/paco-rabanne-1-million-eau-de-toilette-100-ml", "affiliate_url": "https://www.awin1.com/cread.php?awinmid=11672&awinaffid=3099222&clickref=one_million_example61_01&ued=https%3A%2F%2Fwww.perfumetrader.de%2Fde%2Fpaco-rabanne-1-million-eau-de-toilette-100-ml", "network": "Awin", "data_source": "manual_verified_web+awin_verified_deeplink", "commission_rate": null}'::jsonb,'2026-10-02T13:03:47Z');


create or replace function public.dufynd_capability_list_valid(p_value jsonb) returns boolean
language sql immutable security invoker set search_path=public as $$
 select case when jsonb_typeof(p_value) is distinct from 'array' then false
 else jsonb_array_length(p_value)<=32 and not exists(select 1 from jsonb_array_elements(p_value) v
 where jsonb_typeof(v)<>'string' or v#>>'{}' not in ('github.read','github.ci.observe','github.safe_pr','render.observe',
 'supabase.task_state','supabase.execution_state','gmail.read_known_threads','commerce.read','content.read',
 'commerce.verify_exact','commerce.evidence.write','gmail.send','social.publish','budget.spend','main.merge','commerce.activate','shell.execute')) end;
$$;
insert into public.dufynd_handler_contracts(handler_id,handler_version,contract,enabled)
select 'purchase_destination_freshness_audit','1',contract||jsonb_build_object(
 'handler_id','purchase_destination_freshness_audit',
 'capabilities','["commerce.evidence.write","commerce.read","commerce.verify_exact","supabase.execution_state","supabase.task_state"]'::jsonb,
 'required_capabilities','["commerce.evidence.write","commerce.read","commerce.verify_exact","supabase.execution_state","supabase.task_state"]'::jsonb,
 'allowed_scopes','["supervisor"]'::jsonb,
 'allowed_resources','["db:purchase-evidence:perfumetrader-rabanne-1-million-edt-100"]'::jsonb,
 'verification_policy','{"kind":"purchase_destination_freshness_audit","version":1}'::jsonb,
 'certification_status','acceptance_only',
 'allowed_task_ids','["purchase_freshness_acceptance_20261002"]'::jsonb),true
from public.dufynd_handler_contracts where handler_id='durability_probe' and handler_version='1';

create function public.dufynd_purchase_packet_valid(p_payload jsonb) returns boolean
language plpgsql security invoker set search_path=public as $$
declare v public.dufynd_purchase_verification_targets;
begin
 select * into v from public.dufynd_purchase_verification_targets where offer_id=p_payload->>'offer_id';
 return found and p_payload->>'product_id'=v.product_id
 and p_payload->'canonical_identity'=v.canonical_identity and p_payload->'offer_contract'=v.offer_contract
 and p_payload->'allowed_mutations'='["verification_evidence"]'::jsonb
 and p_payload->>'verification_contract'='perfumetrader_exact_html_v1'
 and p_payload->>'steps'='1' and p_payload->>'interval_seconds'='2'
 and p_payload-array['kind','steps','interval_seconds','offer_id','product_id','canonical_identity','offer_contract','last_verified_at','expiry','verification_contract','allowed_mutations']='{}'::jsonb
 and public.dufynd_parse_timestamp(p_payload->>'last_verified_at') is not null
 and public.dufynd_parse_timestamp(p_payload->>'expiry')=public.dufynd_parse_timestamp(p_payload->>'last_verified_at')+interval '72 hours';
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
 -- Selection is stable: lexicographic handler ID/version after all policy filters.
 for h in select * from public.dufynd_handler_contracts where enabled
 and handler_id=p_payload->>'kind' order by handler_id collate "C",handler_version collate "C" loop
  if h.handler_id not in ('durability_probe','supervisor_state_audit','purchase_destination_freshness_audit') or h.handler_version<>'1'
  or (h.handler_id in ('supervisor_state_audit','purchase_destination_freshness_audit') and (coalesce(h.contract->>'certification_status','') not in ('acceptance_only','certified')
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
    or (h.handler_id='purchase_destination_freshness_audit' and r=prefix and r='db:purchase-evidence:perfumetrader-rabanne-1-million-edt-100'))) then continue; end if;
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
 'goal',case when new.handler_id='durability_probe' then 'Verify the bounded arithmetic durability probe' when new.handler_id='purchase_destination_freshness_audit' then 'Verify exact approved merchant identity and persist evidence only; no business field mutations' else 'Persist a bounded read-only supervisor state audit; findings are not repairs or approvals' end,
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
 or coalesce(p_payload->>'kind','') not in ('durability_probe','supervisor_state_audit','purchase_destination_freshness_audit')
 or (p_payload->>'kind'<>'purchase_destination_freshness_audit' and p_payload - array['kind','steps','interval_seconds'] <> '{}'::jsonb)
 or (p_payload->>'kind'='purchase_destination_freshness_audit' and not coalesce(public.dufynd_purchase_packet_valid(p_payload),false))
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
 or t.lease_expires_at<=now() or e.payload->>'kind' not in ('durability_probe','supervisor_state_audit','purchase_destination_freshness_audit') then return null; end if;
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

-- Primary product fields only; never accept prices/stock from cross-sell cards.
create function public.evaluate_dufynd_purchase_page(p_payload jsonb,p_html text,p_shipping text,p_status int,p_shipping_status int) returns jsonb
language plpgsql immutable security invoker set search_path=public as $$
declare title text; sku text; gtin text; price numeric; stock text; decision text; route text; report jsonb;
begin
 if p_status<>200 or p_shipping_status<>200 or octet_length(p_html)>250000 or octet_length(p_shipping)>250000 then
  return jsonb_build_object('version',1,'decision','transport_unverified'); end if;
 title:=substring(p_html from '"productName":"([^"]+)"');
 sku:=substring(p_html from '"productSku":"([^"]+)"');
 gtin:=substring(p_html from '<meta itemprop="gtin13" content="([0-9]+)"');
 price:=substring(p_html from '"productPrice":"([0-9]+[.][0-9]+)"')::numeric;
 stock:=substring(p_html from '<meta itemprop="availability" content="([^"]+)"');
 route:=p_payload->'offer_contract'->>'affiliate_url';
 decision:=case
 when title is distinct from 'Paco Rabanne 1 Million Eau de Toilette 100 ml' then 'variant_identity_mismatch'
 when sku is distinct from p_payload->'canonical_identity'->>'merchant_product_id' then 'merchant_identity_mismatch'
 when gtin is distinct from p_payload->'canonical_identity'->>'gtin' then 'gtin_mismatch'
 when stock is distinct from 'InStock' then 'stock_unverified_or_changed'
 when price is distinct from (p_payload->'offer_contract'->>'price')::numeric then 'price_review_required'
 when position('pauschal mit 4,99 € pro Bestellung' in p_shipping)=0
 or (p_payload->'offer_contract'->>'shipping_cost')::numeric<>4.99 then 'shipping_review_required'
 when p_payload->'offer_contract'->>'product_url' is distinct from 'https://www.perfumetrader.de/de/paco-rabanne-1-million-eau-de-toilette-100-ml'
 or route is distinct from 'https://www.awin1.com/cread.php?awinmid=11672&awinaffid=3099222&clickref=one_million_example61_01&ued=https%3A%2F%2Fwww.perfumetrader.de%2Fde%2Fpaco-rabanne-1-million-eau-de-toilette-100-ml' then 'route_contract_mismatch'
 else 'safe_evidence_refresh' end;
 report:=jsonb_build_object('version',1,'decision',decision,'observed_title',title,'merchant_product_id',sku,'gtin',gtin,
 'price_eur',price,'stock',stock,'shipping_unchanged',position('pauschal mit 4,99 € pro Bestellung' in p_shipping)>0,
 'product_response_hash',encode(sha256(convert_to(p_html,'UTF8')),'hex'),
 'shipping_response_hash',encode(sha256(convert_to(p_shipping,'UTF8')),'hex'),
 'route_validation','exact unchanged approved configuration; no fresh affiliate network click',
 'allowed_mutations',jsonb_build_array('verification_evidence'),'business_mutations',false);
 return report;
end $$;

-- Only net-owned responses to fixed merchant URLs can create durable verification.
create function public.poll_dufynd_purchase_verification(p_execution_id uuid) returns jsonb
language plpgsql security invoker set search_path=public as $$
declare e public.dufynd_execution_runs; product record; shipping record; rid bigint; sid bigint; audit jsonb;
begin
 select * into e from public.dufynd_execution_runs where execution_id=p_execution_id for update;
 if e.handler_id<>'purchase_destination_freshness_audit' or not public.dufynd_execution_contract_valid(e.execution_id) then return null; end if;
 if e.purchase_request_id is null then
  execute 'select net.http_get(url:=$1,headers:=$2,timeout_milliseconds:=10000)' into rid using
   'https://www.perfumetrader.de/de/paco-rabanne-1-million-eau-de-toilette-100-ml','{"Cache-Control":"no-cache","User-Agent":"DUFYND-Exact-Purchase-Verification/1"}'::jsonb;
  execute 'select net.http_get(url:=$1,headers:=$2,timeout_milliseconds:=10000)' into sid using
   'https://www.perfumetrader.de/de/versandbedingungen','{"Cache-Control":"no-cache","User-Agent":"DUFYND-Exact-Purchase-Verification/1"}'::jsonb;
  update public.dufynd_execution_runs set purchase_request_id=rid,purchase_shipping_request_id=sid,purchase_requested_at=now()
   where execution_id=e.execution_id;
  return null;
 end if;
 execute 'select status_code,content,created,timed_out,error_msg from net._http_response where id=$1' into product using e.purchase_request_id;
 if product is null then
  if e.purchase_requested_at<now()-interval '60 seconds' then return jsonb_build_object('version',1,'decision','transport_unverified','observed_at',now()); end if;
  return null;
 end if;
 execute 'select status_code,content,created,timed_out,error_msg from net._http_response where id=$1' into shipping using e.purchase_shipping_request_id;
 if shipping is null then
  if e.purchase_requested_at<now()-interval '60 seconds' then return jsonb_build_object('version',1,'decision','transport_unverified','observed_at',now()); end if;
  return null;
 end if;
 if product.timed_out or shipping.timed_out or product.error_msg is not null or shipping.error_msg is not null
 or product.created<e.purchase_requested_at or shipping.created<e.purchase_requested_at
 or product.created<now()-interval '5 minutes' or shipping.created<now()-interval '5 minutes' then
  return jsonb_build_object('version',1,'decision','transport_unverified','observed_at',now()); end if;
 audit:=public.evaluate_dufynd_purchase_page(e.payload,coalesce(product.content,''),coalesce(shipping.content,''),coalesce(product.status_code,0),coalesce(shipping.status_code,0));
 return audit||jsonb_build_object('observed_at',least(product.created,shipping.created),'source','fixed_https_merchant_pg_net','product_request_id',e.purchase_request_id,'shipping_request_id',e.purchase_shipping_request_id);
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
 if e.handler_id in ('supervisor_state_audit','purchase_destination_freshness_audit') and (jsonb_typeof(e.last_checkpoint->'audit') is distinct from 'object'
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
 -- Verification is the SQL-derived recipe result, never success prose or exit code.
 perform set_config('dufynd.execution_write',e.execution_id::text,true); perform set_config('dufynd.worker_write',p_token::text,true);
 update public.dufynd_autonomy_tasks set status=case when e.handler_id='purchase_destination_freshness_audit' and e.last_checkpoint->'audit'->>'decision'<>'safe_evidence_refresh' then 'blocked' else 'done' end,worker_state='done',evidence='Durable execution '||e.execution_id::text||' verified checkpoint '||e.last_checkpoint::text,
 released_at=now(),lease_expires_at=now(),expected_next_checkpoint=null,blocked_reason=case when e.handler_id='purchase_destination_freshness_audit' and e.last_checkpoint->'audit'->>'decision'<>'safe_evidence_refresh' then e.last_checkpoint->'audit'->>'decision' else null end where task_id=e.task_id;
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
  if e.handler_id='purchase_destination_freshness_audit' and e.status='dispatch_pending' and e.lease_expires_at>now() then
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
   if e.payload->>'kind' not in ('durability_probe','supervisor_state_audit','purchase_destination_freshness_audit') then continue; end if;
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

-- Configured 24h margin: twelve 2-minute watchdog opportunities per retry hour,
-- with time for deployment/review. The 72h customer eligibility gate stays intact.
create function public.wake_dufynd_purchase_freshness() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare v public.dufynd_purchase_verification_targets; tid text; oid text; payload jsonb; fp text; n int:=0;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 for v in select * from public.dufynd_purchase_verification_targets
 where (enabled or certification_due) and (retry_after is null or retry_after<=now())
 and (certification_due or last_verified_at+make_interval(hours=>max_age_hours-safety_window_hours)<=now())
 and (last_result is null or last_result->>'decision' in ('safe_evidence_refresh','transport_unverified')) for update loop
  tid:=case when v.certification_due then 'purchase_freshness_acceptance_20261002'
   else 'purchase-freshness:'||substr(encode(sha256(convert_to(v.offer_id||':'||v.last_verified_at::text||':'||coalesce(v.retry_after::text,''),'UTF8')),'hex'),1,32) end;
  oid:=public.register_dufynd_observer('internal_dependency','purchase-freshness:'||v.offer_id);
  payload:=jsonb_build_object('kind','purchase_destination_freshness_audit','steps',1,'interval_seconds',2,
   'offer_id',v.offer_id,'product_id',v.product_id,'canonical_identity',v.canonical_identity,'offer_contract',v.offer_contract,
   'last_verified_at',v.last_verified_at,'expiry',v.last_verified_at+make_interval(hours=>v.max_age_hours),
   'verification_contract','perfumetrader_exact_html_v1','allowed_mutations',jsonb_build_array('verification_evidence'));
  insert into public.dufynd_autonomy_tasks(task_id,domain,title,instruction,status,budget_class,durability_policy,resource_scope,durable_payload,required_capabilities,forbidden_actions)
  values(tid,'supervisor','Exact purchase evidence verification','Verify the compiled merchant contract only; no business mutations.','waiting_external','free','durable',
   jsonb_build_array('db:purchase-evidence:'||v.offer_id),payload,
   '["commerce.evidence.write","commerce.read","commerce.verify_exact","supabase.execution_state","supabase.task_state"]',
   '["gmail.send","social.publish","budget.spend","main.merge","commerce.activate","shell.execute"]') on conflict do nothing;
  perform public.bind_dufynd_external_wait(tid,oid,'["purchase.freshness.due"]');
  fp:=encode(sha256(convert_to('purchase.freshness.due:'||tid,'UTF8')),'hex');
  insert into public.dufynd_jarvis_inbox(event_type,source_type,source_id,payload,fingerprint,related_task_ids)
  values('purchase.freshness.due','internal_dependency',v.offer_id,
   jsonb_build_object('observer_id',oid,'evidence',jsonb_build_object('offer_id',v.offer_id,'expiry',payload->'expiry','wake_reason',case when v.certification_due then 'initial_certification' else 'pre_expiry' end)),fp,jsonb_build_array(tid))
   on conflict(fingerprint) where fingerprint is not null do nothing;
  if found then n:=n+1; end if;
 end loop;
 return jsonb_build_object('wake_events',n);
end $$;

create function public.certify_dufynd_purchase_freshness(p_execution_id uuid) returns boolean
language plpgsql security invoker set search_path=public as $$
declare e public.dufynd_execution_runs;
begin
 select * into e from public.dufynd_execution_runs where execution_id=p_execution_id;
 if not found or e.task_id<>'purchase_freshness_acceptance_20261002' or e.status<>'completed'
 or e.handler_id<>'purchase_destination_freshness_audit'
 or e.last_checkpoint->'audit'->>'decision'<>'safe_evidence_refresh'
 or e.last_checkpoint->>'audit_hash' is distinct from encode(sha256(convert_to((e.last_checkpoint->'audit')::text,'UTF8')),'hex')
 or not exists(select 1 from public.dufynd_autonomy_tasks where task_id=e.task_id and status='done' and released_at is not null)
 or not exists(select 1 from public.dufynd_purchase_verification_evidence where execution_id=e.execution_id and decision='safe_evidence_refresh' and report_hash=e.last_checkpoint->>'audit_hash') then return false; end if;
 update public.dufynd_handler_contracts set contract=contract||jsonb_build_object('certification_status','certified','certification_execution_id',e.execution_id,'certified_at',now())
 where handler_id='purchase_destination_freshness_audit' and handler_version='1';
 update public.dufynd_purchase_verification_targets set enabled=true,certification_due=false where offer_id=e.payload->>'offer_id';
 return true;
end $$;

-- Authenticated internal read; no new public HTTP commerce route or anonymous grant.
create function public.read_dufynd_purchase_evidence(p_offer_id text) returns jsonb
language sql stable security invoker set search_path=public as $$
select jsonb_build_object('offer_contract',v.offer_contract,'verified_at',v.last_verified_at,
 'decision',v.last_result->>'decision','source','certified_purchase_verification','max_age_hours',v.max_age_hours)
from public.dufynd_purchase_verification_targets v join public.dufynd_handler_contracts h
 on h.handler_id='purchase_destination_freshness_audit' and h.handler_version='1'
where v.offer_id=p_offer_id and v.enabled and h.enabled and h.contract->>'certification_status'='certified';
$$;

create or replace function public.reconcile_dufynd_supervisor_v2() returns jsonb
language plpgsql security invoker set search_path=public as $$
declare observers jsonb; events jsonb; prior jsonb; receipts jsonb;
begin
 perform pg_advisory_xact_lock(hashtext('dufynd-supervisor-v2-claims'));
 -- claim_worker calls the supervisor: avoid recursive event -> prepare -> claim -> event.
 if current_setting('dufynd.event_processing',true)='true' then return public.reconcile_dufynd_supervisor_v2_phase2b(); end if;
 begin
  perform public.wake_dufynd_purchase_freshness();
  observers:=public.poll_dufynd_observers();
 exception when others then
  -- A transport/extension outage cannot stop leases, reservations or executions.
  observers:=jsonb_build_object('available',false,'error','observer_transport_unavailable','sqlstate',sqlstate);
  update public.dufynd_external_observers set health_status='degraded',last_error='observer_transport_unavailable',consecutive_failures=consecutive_failures+1,next_retry_at=now()+interval '5 minutes' where enabled and source_type<>'internal_dependency' and health_status<>'blocked_configuration';
 end;
 begin
  events:=public.process_dufynd_external_events();
 exception when others then
  events:=jsonb_build_object('processed',0,'error','event_reevaluation_retryable','sqlstate',sqlstate);
  perform set_config('dufynd.event_processing','',true);
  perform set_config('dufynd.worker_write','',true);
 end;
 prior:=public.reconcile_dufynd_supervisor_v2_phase2b();
 receipts:=public.project_dufynd_acceptance_receipts();
 update public.dufynd_master_status set value=value||jsonb_build_object('acceptance_receipts',receipts,'observer_health',public.get_dufynd_observer_health(),'external_events',events,'observer_poll',observers) where key='jarvis.supervisor_v2.health';
 return prior||jsonb_build_object('acceptance_receipts',receipts,'observer_health',public.get_dufynd_observer_health(),'external_events',events);
end $$;

do $$ declare f record; begin
 for f in select oid::regprocedure signature from pg_proc where pronamespace='public'::regnamespace and proname in
 ('dufynd_purchase_packet_valid','evaluate_dufynd_purchase_page','poll_dufynd_purchase_verification','wake_dufynd_purchase_freshness','certify_dufynd_purchase_freshness','read_dufynd_purchase_evidence') loop
 execute 'revoke all on function '||f.signature||' from public,anon,authenticated';
 execute 'grant execute on function '||f.signature||' to service_role';
 end loop;
end $$;
