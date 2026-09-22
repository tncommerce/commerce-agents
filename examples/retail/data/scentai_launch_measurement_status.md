# DUFYND Organic Launch Measurement Status

Status: deployed_verified
Updated: 2026-09-22

## Prepared

- first-party session attribution for acquisition channel, campaign ID and
  content ID
- privacy-safe identifier validation in frontend and API
- Supabase schema/view update prepared in the repo
- content-level acquisition reporting prepared
- standardized campaign-link builder
- 15-creatives pre-launch content plan
- all 15 pre-launch creatives scripted in three guarded production batches
- all 15 scripted creatives have scene-level production packs with approved
  DUFYND product-image references, overlay/component instructions and CTA
  endcards
- three organic channels: TikTok, Instagram and YouTube
- 45 standardized creative/channel link combinations available through the
  launch-link exporter
- regression coverage for campaign links, analytics metadata, conversion
  reporting, content-plan integrity and analytics-SQL duplication

## Production state

The production Supabase analytics schema has been migrated and verified.
The live analytics table now accepts:
- `acquisition_source`
- `campaign_id`
- `content_id`

The `scentai_acquisition_funnel` reporting view is deployed alongside the existing conversion, product, clickout and retention views. The migration remained additive/idempotent, RLS stays enabled, and reporting views use `security_invoker = true`.

## Pre-launch smoke test

Database migration is complete. After the matching frontend attribution deployment:

1. Open one tracked TikTok link.
2. Start a consultation.
3. Open a fragrance detail.
4. Trigger a test merchant clickout only when a valid merchant offer exists.
5. Verify the acquisition report preserves the same channel, campaign and
   content ID through the session.
6. Repeat one Instagram and one YouTube link.
7. Confirm an untracked direct visit is attributed as organic without changing
   the historical landing-source key.

## Current operating state

The legacy production-pack workflow is retained as a reference/utility system,
but public-facing copy has been rebranded to DUFYND. Paid creative generation
is not the current bottleneck. Commerce readiness — especially the real
Perfumetrader/Awin product feed, product-level tracked offers and production
image approval — remains the active priority.

## Next operating block

After commerce readiness and explicit publishing approval, use the production
packs as an executable editing workflow:
- reusable 9:16 editing template
- subtitle and on-screen text layout rules
- voiceover recording workflow
- final tracked link assignment per channel
- pre-publish claim and link QA
- first rendered pilot creative before scaling the remaining 14
