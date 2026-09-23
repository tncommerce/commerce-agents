# DUFYND Soft-Launch Measurement Playbook — 2026-09-23

## Objective

Use the 2026-09-26 soft launch to discover repeatable content-to-site behavior, not to chase isolated view spikes.

## Measurement layers

### 1. Platform attention

Capture per post where available:
- views / reach;
- average watch time or average percentage watched;
- completion rate;
- saves;
- shares;
- comments;
- follows or profile visits attributable to the post.

These are attention signals, not revenue proof.

### 2. DUFYND qualified traffic

Use first-party acquisition attribution:
- `src` = tiktok / instagram / youtube;
- `cmp` = `launch01`;
- `content` = canonical DUFYND content ID.

Primary site metrics:
- landing sessions by content ID;
- landing → consultation start;
- fragrance-detail sessions;
- comparison sessions;
- catalog no-result searches;
- merchant-clickout sessions.

### 3. Commercial intent

Treat merchant clickout as a downstream intent signal, not as a completed sale.

Do not let affiliate commission influence:
- fragrance recommendations;
- content winner selection;
- merchant ordering presented to the user.

## Review cadence

### First 24 hours after a post

Goal: technical integrity.

Check:
- post published correctly on the intended platform;
- tracked DUFYND link resolves;
- acquisition source / campaign / content ID appears in analytics;
- no wrong product identity, price claim or broken CTA;
- obvious comment themes or misunderstandings.

Do **not** call a creative a winner or loser from the first hours unless there is a clear quality/compliance failure.

### Around 72 hours

Goal: first directional signal.

Compare:
- attention quality, not raw views only;
- saves + shares relative to reach;
- follows/profile actions;
- DUFYND landing sessions;
- qualified site actions after landing.

Ask:
- Did the hook earn attention?
- Did the format create save/share behavior?
- Did the post create curiosity strong enough to reach DUFYND?
- Once on DUFYND, did users continue into detail, comparison or advisor behavior?

### Weekly review

Goal: decide what to repeat.

Group by format, for example:
- cinematic product hero;
- educational myth-busting;
- original / alternative comparison;
- advisor / occasion;
- desire / “I want to smell…” static.

Only materially scale a format after at least three comparable executions where practical.

Use the median of comparable posts as the internal baseline rather than comparing every post to the single highest-view outlier.

## Decision rules

### Repeat / scale

A format should receive more production capacity when it repeatedly shows a strong combination of:
- attention retention;
- saves/shares or follows;
- qualified DUFYND landing sessions;
- downstream detail/comparison/advisor activity.

### Revise

Keep the concept but change execution when:
- the topic gets site interest but weak watch/scroll-stop;
- watch quality is strong but CTA/site transfer is weak;
- comments reveal repeated misunderstanding;
- visual quality is below the current Naxos/Bois benchmark.

### Stop

Pause a direction when repeated comparable tests show weak attention **and** weak qualified site behavior, or when exact-product/compliance accuracy cannot be maintained economically.

## Pre-launch baseline

Reference:
- `examples/retail/data/dufynd_prelaunch_analytics_baseline_20260923.json`

The baseline includes internal/smoke activity. Post-launch evaluation should prefer records with:
- `campaign_id = launch01`
- a known `content_id`
- a known acquisition source.

## Current prepared launch attribution

Reference:
- `examples/retail/data/dufynd_launch_tracking_links_20260923.json`

## Weekly operator output

Produce one compact decision memo:

1. What generated attention?
2. What generated qualified DUFYND traffic?
3. What generated downstream intent?
4. What did users ask for or fail to find?
5. Which 3–5 formats deserve the next production block?
6. Which catalog/website gap should be fixed because demand exposed it?
7. What should **not** receive more time or money next week?

The goal is a learning loop: content reveals demand → analytics identifies intent → catalog/site improves → stronger content sends better-qualified users back into DUFYND.
