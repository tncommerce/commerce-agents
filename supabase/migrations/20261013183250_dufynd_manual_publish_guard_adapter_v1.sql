-- SAFETY-08: UNAPPLIED. Exact PR783 guard plus fail-closed adapter readiness.
-- Install only with separate Owner GO; no jobs, schedules or publication grants.
-- DEVELOPMENT PROPOSAL ONLY. Generate/review a migration before any deployment.
-- Reuses master-status receipts and the existing dispatch ledger; no new queue.
create function public.record_dufynd_manual_delivery_v1(
 p_content_id text, p_platform text, p_asset_sha256 text, p_state text,
 p_provider_post_id text, p_provider_uuid text, p_evidence_ref text
) returns jsonb language plpgsql security invoker set search_path=public as $$
declare k text; prior jsonb; state text; conflict boolean;
begin
 if coalesce(p_content_id,'') !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$'
  or p_platform is null or p_platform not in ('instagram','tiktok','youtube')
  or coalesce(p_asset_sha256,'') !~ '^[a-f0-9]{64}$'
  or p_state is null or p_state not in ('MANUAL_PENDING','MANUAL_PUBLISHED','MANUAL_UNKNOWN')
  or coalesce(p_provider_post_id,'') !~ '^[0-9]{1,30}$'
  or coalesce(p_provider_uuid,'') !~ '^-?[0-9]{1,30}$'
  or coalesce(p_evidence_ref,'') !~ '^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$'
 then raise exception 'invalid_manual_delivery'; end if;
 -- Shared with the dispatch trigger, across all platforms to avoid lock-order
 -- inversions during existing atomic multi-platform reservations.
 perform pg_advisory_xact_lock(7182186, 606);
 k:='content.manual_delivery:7182186:'||p_platform||':'||p_content_id;
 select value into prior from public.dufynd_master_status where key=k for update;
 if found and (prior->>'asset_sha256' is distinct from p_asset_sha256
  or prior->>'provider_post_id' is distinct from p_provider_post_id
  or prior->>'provider_uuid' is distinct from p_provider_uuid) then
  raise exception 'manual_identity_conflict'; end if;
 if exists(select 1 from public.dufynd_master_status where key like 'content.manual_delivery:7182186:%'
  and key<>k and value->>'platform'=p_platform and
   (value->>'asset_sha256'=p_asset_sha256 or value->>'provider_post_id'=p_provider_post_id
    or value->>'provider_uuid'=p_provider_uuid)) then
  raise exception 'manual_alias_requires_reconciliation'; end if;
 -- Published is a terminal fact. Uncertainty also never reopens automation.
 state:=case when prior->>'state'='MANUAL_PUBLISHED' then 'MANUAL_PUBLISHED'
             when prior->>'state'='MANUAL_UNKNOWN' and p_state='MANUAL_PENDING' then 'MANUAL_UNKNOWN'
             else p_state end;
 select exists(select 1 from public.dufynd_publish_dispatches where brand_id='7182186'
  and platform=p_platform and (content_id=p_content_id or asset_sha256=p_asset_sha256)) into conflict;
 insert into public.dufynd_master_status(key,category,value) values(k,'content',jsonb_build_object(
  'content_id',p_content_id,'platform',p_platform,'brand_id','7182186','asset_sha256',p_asset_sha256,
  'state',state,'provider_post_id',p_provider_post_id,'provider_uuid',p_provider_uuid,
  'evidence_ref',p_evidence_ref,'observed_at',clock_timestamp(),'auto_publish_allowed',false,
  'existing_dispatch_requires_reconciliation',conflict))
 on conflict(key) do update set value=excluded.value,updated_at=now();
 return jsonb_build_object('recorded',true,'state',state,'auto_publish_allowed',false,
  'existing_dispatch_requires_reconciliation',conflict);
end $$;

create function public.guard_dufynd_manual_delivery_v1() returns trigger
language plpgsql security invoker set search_path=public as $$
declare canonical text;
begin
 -- Receipt recording after a provider call must remain possible, even after a
 -- late manual observation. Fence only reservation and the one-time invocation.
 if TG_OP='UPDATE' then
  if new.receipt->'invocation_claimed' is distinct from 'true'::jsonb
   or old.receipt->'invocation_claimed'='true'::jsonb then return new; end if;
 end if;
 perform pg_advisory_xact_lock(7182186, 606);
 select metadata->>'release_content_id' into canonical from public.dufynd_content_assets where id=new.asset_id;
 if exists(select 1 from public.dufynd_master_status where key like 'content.manual_delivery:7182186:%'
  and value->>'platform'=new.platform and
   (value->>'content_id'=new.content_id or value->>'content_id'=canonical
    or value->>'asset_sha256'=new.asset_sha256)) then
  -- Presence itself blocks, including corrupt/unknown states. No expiry or
  -- pending notification may turn a manual-only creative back into automatic.
  raise exception 'manual_delivery_blocks_automatic_dispatch';
 end if;
 return new;
end $$;

create trigger dufynd_manual_delivery_dispatch_guard
 before insert or update of receipt on public.dufynd_publish_dispatches
 for each row execute function public.guard_dufynd_manual_delivery_v1();

revoke all on function public.record_dufynd_manual_delivery_v1(text,text,text,text,text,text,text),
 public.guard_dufynd_manual_delivery_v1() from public,anon,authenticated;
grant execute on function public.record_dufynd_manual_delivery_v1(text,text,text,text,text,text,text),
 public.guard_dufynd_manual_delivery_v1() to service_role;

-- DEVELOPMENT PROPOSAL. Apply only after the exact PR783 guard SQL, with GO.
-- Read-only capability gate for the existing connected publisher entry points.
create function public.dufynd_manual_guard_ready_v1() returns boolean
language sql stable security invoker set search_path=pg_catalog as $$
 select current_setting('session_replication_role')='origin'
 and to_regprocedure('public.record_dufynd_manual_delivery_v1(text,text,text,text,text,text,text)') is not null
 and exists (
   select 1 from pg_trigger t join pg_attribute a
     on a.attrelid=t.tgrelid and a.attname='receipt' and not a.attisdropped
   where t.tgrelid=to_regclass('public.dufynd_publish_dispatches')
     and t.tgname='dufynd_manual_delivery_dispatch_guard'
     and t.tgfoid=to_regprocedure('public.guard_dufynd_manual_delivery_v1()')
     and t.tgenabled in ('O','A') and not t.tgisinternal
     and t.tgtype=23 and t.tgqual is null and t.tgnargs=0
     and t.tgattr::text=a.attnum::text
 );
$$;
revoke all on function public.dufynd_manual_guard_ready_v1() from public,anon,authenticated;
grant execute on function public.dufynd_manual_guard_ready_v1() to service_role;
