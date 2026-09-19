# SCENTAI Organic Launch Measurement Status

Status: prepared_not_deployed
Updated: 2026-09-19

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
  SCENTAI product-image references, overlay/component instructions and CTA
  endcards
- three organic channels: TikTok, Instagram and YouTube
- 45 standardized creative/channel link combinations available through the
  launch-link exporter
- regression coverage for campaign links, analytics metadata, conversion
  reporting, content-plan integrity and analytics-SQL duplication

## Production state

The code is prepared on the `scentai-mvp` branch but the new Supabase
analytics columns/view have not been applied to the production database in this
work block.

Do not deploy the frontend attribution payload before the production analytics
schema accepts:
- `acquisition_source`
- `campaign_id`
- `content_id`

The SQL remains additive/idempotent and keeps RLS enabled. Reporting views use
`security_invoker = true`.

## Pre-launch smoke test

After database migration and deployment:

1. Open one tracked TikTok link.
2. Start a consultation.
3. Open a fragrance detail.
4. Trigger a test merchant clickout only when a valid merchant offer exists.
5. Verify the acquisition report preserves the same channel, campaign and
   content ID through the session.
6. Repeat one Instagram and one YouTube link.
7. Confirm an untracked direct visit is attributed as organic without changing
   the historical landing-source key.

## Next operating block

Turn the production packs into an executable editing workflow:
- reusable 9:16 editing template
- subtitle and on-screen text layout rules
- voiceover recording workflow
- final tracked link assignment per channel
- pre-publish claim and link QA
- first rendered pilot creative before scaling the remaining 14
