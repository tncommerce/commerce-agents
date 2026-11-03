-- DUFYND: runtime merchant observations, independent of website Git releases.
-- PREPARED ONLY. Apply after separate Owner production/DB GO.
-- No new SKU, merchant route or network link is stored here.
-- Source evidence timestamp, NOT database write time, controls the 72h gate.

create table if not exists public.dufynd_runtime_offer_snapshots_v1 (
  offer_id text primary key check (offer_id ~ '^[A-Za-z0-9._:-]{1,120}$'),
  product_id text not null check (product_id ~ '^[A-Za-z0-9._:-]{1,120}$'),
  merchant_id text not null check (merchant_id ~ '^[A-Za-z0-9._:-]{1,120}$'),
  merchant_product_id text,
  identity_sha256 text not null check (identity_sha256 ~ '^[0-9a-f]{64}$'),
  currency text not null default 'EUR' check (currency = 'EUR'),
  -- A HOLD must not duplicate a historical amount or invent a stock claim.
  price numeric(12,2) check (price is null or (price > 0 and price <= 100000)),
  shipping_cost numeric(12,2) check (shipping_cost >= 0 and shipping_cost <= 100000),
  in_stock boolean,
  verified_at timestamptz not null,
  -- Trigger-owned replay barrier, never a price-freshness timestamp. A HOLD
  -- keeps its real observation time even after a source clock ran ahead.
  source_watermark_at timestamptz not null check (source_watermark_at >= verified_at),
  decision text not null check (decision in ('verified','hold')),
  constraint dufynd_runtime_offer_decision_values_check check (
    (decision = 'verified' and price is not null
      and shipping_cost is not null and in_stock is true)
    or (decision = 'hold' and price is null
      and shipping_cost is null and in_stock is null)
  ),
  source_type text not null check (
    source_type in ('official_network_feed','authorized_merchant_api','direct_merchant_review')
  ),
  source_ref text not null check (char_length(source_ref) between 3 and 260),
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.dufynd_runtime_offer_snapshot_audit_v1 (
  audit_id bigint generated always as identity primary key,
  offer_id text not null,
  changed_at timestamptz not null default now(),
  changed_by text not null default current_user,
  prior_row jsonb,
  next_row jsonb not null
);

-- Every source observation changes via the server-side service role only.
alter table public.dufynd_runtime_offer_snapshots_v1 enable row level security;
alter table public.dufynd_runtime_offer_snapshot_audit_v1 enable row level security;
revoke all on public.dufynd_runtime_offer_snapshots_v1 from public, anon, authenticated;
revoke all on public.dufynd_runtime_offer_snapshot_audit_v1 from public, anon, authenticated;
grant select, insert, update on public.dufynd_runtime_offer_snapshots_v1 to service_role;
grant select, insert on public.dufynd_runtime_offer_snapshot_audit_v1 to service_role;
grant usage on sequence public.dufynd_runtime_offer_snapshot_audit_v1_audit_id_seq
  to service_role;

-- No DELETE grant, no anon/auth policies, no public RPC.
create or replace function public.dufynd_runtime_offer_snapshot_guard_v1()
returns trigger
language plpgsql
security invoker
set search_path = pg_catalog, public
as $function$
begin
  if new.verified_at > clock_timestamp() + interval '5 minutes' then
    raise exception 'verified_at cannot be in the future';
  end if;
  if new.decision = 'verified'
     and new.verified_at < clock_timestamp() - interval '72 hours' then
    raise exception 'only fresh observations can be marked verified';
  end if;
  if tg_op = 'UPDATE' and (
     new.offer_id is distinct from old.offer_id
     or new.product_id is distinct from old.product_id
     or new.merchant_id is distinct from old.merchant_id
     or new.merchant_product_id is distinct from old.merchant_product_id
     or new.identity_sha256 is distinct from old.identity_sha256
     or new.currency is distinct from old.currency
  ) then
    raise exception 'canonical offer identity is immutable';
  end if;
  if tg_op = 'UPDATE' then
    -- A fail-closed withdrawal cannot wait for a same-time or clock-skewed
    -- positive observation. Every other update, including reactivation, must
    -- advance beyond the highest source time ever accepted for this identity.
    if not (old.decision = 'verified' and new.decision = 'hold')
       and new.verified_at <= old.source_watermark_at then
      raise exception 'observation timestamps must advance strictly';
    end if;
    new.source_watermark_at := greatest(old.source_watermark_at, new.verified_at);
  else
    new.source_watermark_at := new.verified_at;
  end if;
  -- Ignore any caller-supplied watermark without rewriting the source time.
  new.updated_at := clock_timestamp();
  return new;
end;
$function$;

create or replace function public.dufynd_runtime_offer_snapshot_audit_v1()
returns trigger
language plpgsql
security invoker
set search_path = pg_catalog, public
as $function$
begin
  insert into public.dufynd_runtime_offer_snapshot_audit_v1
      (offer_id, prior_row, next_row)
  values
      (new.offer_id, case when tg_op = 'UPDATE' then to_jsonb(old) else null end,
       to_jsonb(new));
  return new;
end;
$function$;

revoke all on function public.dufynd_runtime_offer_snapshot_guard_v1() from public;
revoke all on function public.dufynd_runtime_offer_snapshot_audit_v1() from public;
grant execute on function public.dufynd_runtime_offer_snapshot_guard_v1()
  to service_role;
grant execute on function public.dufynd_runtime_offer_snapshot_audit_v1()
  to service_role;

drop trigger if exists dufynd_runtime_offer_snapshot_guard
  on public.dufynd_runtime_offer_snapshots_v1;
create trigger dufynd_runtime_offer_snapshot_guard
before insert or update on public.dufynd_runtime_offer_snapshots_v1
for each row execute function public.dufynd_runtime_offer_snapshot_guard_v1();

drop trigger if exists dufynd_runtime_offer_snapshot_audit
  on public.dufynd_runtime_offer_snapshots_v1;
create trigger dufynd_runtime_offer_snapshot_audit
after insert or update on public.dufynd_runtime_offer_snapshots_v1
for each row execute function public.dufynd_runtime_offer_snapshot_audit_v1();

create index if not exists dufynd_runtime_offer_snapshots_verified_idx
on public.dufynd_runtime_offer_snapshots_v1 (verified_at desc);
