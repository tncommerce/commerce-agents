# DUFYND Soft-Launch Runbook — 2026-09-26

## Goal

Launch DUFYND with the two approved premium masters first, preserve the Naxos quality floor, verify attribution end-to-end, and collect useful audience/site signals without turning the first 72 hours into a vanity-metric reaction loop.

## Hard gates

- Public brand: DUFYND.
- Launch campaign ID: `launch01`.
- Quality floor for new premium video: Naxos campaign final.
- Approved launch order #1: `naxos_campaign_final`.
- Approved launch order #2: `bois_imperial_final`.
- Review-pending assets are **not** publishable until explicitly approved.
- No paid AI generation is required for launch execution.
- Affiliate commission must not affect editorial recommendations or merchant ordering.

## T-24h checklist

1. Confirm TikTok, Instagram and YouTube channels still show DUFYND branding.
2. Confirm profile website link points to `https://dufynd.de` where the platform permits it.
3. Confirm the approved Naxos and Bois master files open correctly on the operator device.
4. Confirm no watermark, crop or export issue was introduced by a later edit.
5. Use the prepared platform copy from:
   - `examples/retail/data/dufynd_social_copy_20260923.json`
6. Use the prepared tracked links from:
   - `examples/retail/data/dufynd_launch_tracking_links_20260923.json`
7. Do not add a price claim unless it is reverified immediately before publishing.
8. Do not make new similarity percentages or "1:1" claims.

## Launch post #1 — Naxos

Content ID:
`naxos_campaign_final`

Landing:
`/duft/xerjoff-naxos`

Tracking:
- TikTok: `https://dufynd.de/duft/xerjoff-naxos?src=tiktok&cmp=launch01&content=naxos_campaign_final`
- Instagram: `https://dufynd.de/duft/xerjoff-naxos?src=instagram&cmp=launch01&content=naxos_campaign_final`
- YouTube: `https://dufynd.de/duft/xerjoff-naxos?src=youtube&cmp=launch01&content=naxos_campaign_final`

Execution:
1. Upload the approved master without re-encoding unless the platform requires it.
2. Check first frame / cover selection before publishing.
3. Apply the prepared channel copy.
4. Where a clickable external link is unavailable inside the post, keep the tracked link in the profile/description surface that the platform supports and keep the content ID documented.
5. Publish only after final operator preview.

Immediate QA:
- video plays;
- text is inside safe areas;
- audio level is normal;
- caption has no typo;
- DUFYND profile and destination are correct.

## Launch post #2 — Bois Impérial

Content ID:
`bois_imperial_final`

Landing:
`/duft/essential-parfums-bois-imperial`

Tracking:
- TikTok: `https://dufynd.de/duft/essential-parfums-bois-imperial?src=tiktok&cmp=launch01&content=bois_imperial_final`
- Instagram: `https://dufynd.de/duft/essential-parfums-bois-imperial?src=instagram&cmp=launch01&content=bois_imperial_final`
- YouTube: `https://dufynd.de/duft/essential-parfums-bois-imperial?src=youtube&cmp=launch01&content=bois_imperial_final`

Use the same upload QA sequence as Naxos.

## Review-pending reserve

Only use after explicit creative approval:
- `sillage_vs_haltbarkeit_01`
- `original_vs_alt_imagination_01`
- `not_every_dupe_clone_01`
- `top3_office_01`
- `i_want_to_smell_naxos_01`

Fallback rule:
If one of these does not meet the visual standard, skip it. Do not publish weaker content merely to fill a calendar slot.

## First-hour technical check

For each published platform post:
1. Confirm the public post is visible.
2. Confirm the intended cover/thumbnail survived upload.
3. Confirm caption/title formatting.
4. Confirm any used DUFYND link resolves.
5. Confirm first-party attribution starts appearing with the correct:
   - source;
   - campaign `launch01`;
   - content ID.
6. Screenshot any platform-side anomaly before editing/deleting the post.

Do not delete/re-upload for minor non-functional differences that do not harm quality, because that destroys the clean performance baseline.

## 24-hour review

Purpose: technical and qualitative integrity, **not** a winner/loser decision.

Capture where available:
- views/reach;
- watch time / completion;
- saves;
- shares;
- comments;
- profile visits/follows;
- DUFYND attributed landing sessions;
- downstream detail/comparison/advisor events.

Also record:
- recurring comment themes;
- requests for specific fragrances;
- confusion about a claim;
- obvious mobile/site friction.

## 72-hour review

Compare post behavior using:
- attention quality;
- saves/shares;
- follows/profile actions;
- qualified DUFYND landing sessions;
- detail/comparison/advisor continuation;
- merchant clickouts only as downstream intent.

Do not materially change strategy from one post unless there is a quality, accuracy or compliance failure.

## Content decision after first wave

Classify each format:
- **repeat** — strong combination of attention and qualified site behavior;
- **revise** — useful topic, weak execution or weak CTA transfer;
- **pause** — weak attention and weak qualified behavior across comparable tests.

Do not call a format a scalable winner until there are preferably three comparable executions.

## Commercial handoff

Audience/content data may inform:
- which catalog gaps deserve priority;
- which Next-10 products should be unlocked next;
- which affiliate applications are worth revisiting.

It must not change editorial recommendations merely because a merchant pays more commission.

## Operator references

- Publish matrix: `examples/retail/data/dufynd_launch_publish_matrix_20260923.json`
- Content buffer: `examples/retail/data/dufynd_content_buffer_plan.json`
- Social copy: `examples/retail/data/dufynd_social_copy_20260923.json`
- Tracking links: `examples/retail/data/dufynd_launch_tracking_links_20260923.json`
- Measurement playbook: `docs/dufynd_launch_measurement_playbook_20260923.md`
- Prelaunch baseline: `examples/retail/data/dufynd_prelaunch_analytics_baseline_20260923.json`
- Review pack: `docs/dufynd_review_pack_20260923.md`
