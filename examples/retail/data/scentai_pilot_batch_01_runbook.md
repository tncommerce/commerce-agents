# SCENTAI Pilot Batch 01 — Production Runbook

Status: production-ready
Updated: 2026-09-19

## Scope

This runbook operationalizes `scentai_pilot_batch_01.json` for the first five
short-form launch pilots across TikTok, Instagram Reels and YouTube Shorts.

## Production order

1. original_vs_alt_imagination_01
2. budget_three_under_50_01
3. not_every_dupe_clone_01
4. top3_office_01
5. bois_imperial_explained_01

The order intentionally alternates purchase-intent, value, education, advisor
utility and fragrance deep-dive formats so early launch data does not come from
five nearly identical creatives.

## Visual system

- Canvas: 1080 x 1920
- Aspect ratio: 9:16
- Frame rate: 30 fps
- Hook text visible within the first second
- Maximum 2-3 subtitle lines at once
- Use one consistent SCENTAI endcard
- Keep product imagery accurate; never use a bottle image that materially
  misrepresents the real product
- Prefer existing approved SCENTAI editorial assets where available

## Voiceover

- Conversational German
- Calm, confident and compact
- No exaggerated sales language
- Speak product relationship labels exactly as stored in SCENTAI
- Community-derived performance metrics must be framed as community data
- Avoid unsupported superlatives such as “best”, “perfect” or “1:1” unless
  the claim is explicitly supported by the current SCENTAI evidence model

## Audio

- Voiceover remains clearly above music
- Music should not compete with speech
- Leave 2-3 seconds for the final CTA/endcard

## Price claims

Any creative containing a numeric price must be rechecked on publish day.

If the observed market price exceeds the headline threshold, update or remove
that claim before publishing. Never preserve a stale “under 50 €” headline just
to keep the creative unchanged.

## Tracking

Campaign:
`launch01`

Use the same content ID across TikTok, Instagram and YouTube. Channel attribution
is supplied separately through `src`.

Tracked link format:

```text
?src=<channel>&cmp=launch01&content=<content_id>
```

Primary first-party outcomes:
- consultation start
- recommendation view
- fragrance detail view
- comparison start
- merchant clickout

A merchant clickout is not a verified purchase.

## Pre-publish QA

For every video verify:

1. Correct fragrance identity and bottle asset
2. Correct relationship wording (clone / inspired / alternative)
3. No invented similarity percentages
4. No stale numeric price claim
5. No affiliate-commission influence on fragrance ordering
6. Subtitle readability on mobile
7. CTA matches the configured landing page
8. Content ID matches the manifest
9. Tracked link uses the correct channel
10. Final render viewed once without editor overlays

## Pilot evaluation

Do not declare a format successful or unsuccessful from a single upload.

Evaluate:
- social-platform completion/watch data
- profile/link engagement
- SCENTAI landing sessions
- consultation starts
- comparisons
- merchant clickouts

Early results are directional. Strong formats should receive 3-5 controlled
variants before larger conclusions are drawn.

## Scaling rule

A winning format becomes a reusable content series, not a one-off repost.

Examples:
- Original vs Alternative -> new fragrance clusters
- Budget Top 3 -> new budget bands / seasons / occasions
- Education / Trust -> additional SCENTAI methodology explanations
- Occasion Advisor -> date, summer, winter, everyday, party
- Deep Dive -> one fragrance per episode

Customer usefulness and recommendation integrity remain more important than
affiliate monetization.
