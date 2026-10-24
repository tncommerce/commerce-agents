-- DEV-ONLY; no live migration or price activation without owner release GO.
-- Private, RLS-protected runtime verification of already-registered Git offers.
-- This stores observed volatile values; it does not independently verify Notino.
CREATE TABLE IF NOT EXISTS public.dufynd_live_offer_snapshots (
  offer_id text PRIMARY KEY CHECK (offer_id ~ '^[A-Za-z0-9._:-]{1,120}$'),
  identity_sha256 text NOT NULL CHECK (identity_sha256 ~ '^[0-9a-f]{64}$'),
  verification_method text NOT NULL CHECK (verification_method = 'certified_merchant_observation'),
  source_url text NOT NULL CHECK (source_url ~ '^https://[^[:space:]]+$'),
  price double precision NOT NULL CHECK (price > 0 AND price < 100000),
  shipping_cost double precision CHECK (
    shipping_cost IS NULL OR (shipping_cost >= 0 AND shipping_cost < 10000)
  ),
  shipping_label text CHECK (shipping_label IS NULL OR length(shipping_label) <= 160),
  in_stock boolean NOT NULL,
  currency text NOT NULL CHECK (currency = 'EUR'),
  verified_at timestamptz NOT NULL,
  evidence_reference text NOT NULL CHECK (length(evidence_reference) BETWEEN 12 AND 500),
  inserted_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.dufynd_live_offer_snapshots ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.dufynd_live_offer_snapshots FROM public, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.dufynd_live_offer_snapshots TO service_role;
-- Only privileged server verification may upsert. No public client write policy.
-- Price age, source URL, product identity and approved tracked destination are
-- validated again on each server-side read (fail closed, 72-hour expiry).
