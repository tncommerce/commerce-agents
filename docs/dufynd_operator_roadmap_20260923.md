# DUFYND Operator Roadmap — 2026-09-23

## Purpose

This document is the current operator-level control view for DUFYND. It is intentionally narrower than the historical project documentation: it records what matters now, what can run in parallel, what is blocked, and what requires explicit operator approval.

## Operating principles

1. Protect the 2026-09-26 soft launch.
2. Prefer completion and distribution of strong existing work over producing more inventory.
3. Run independent tracks in parallel when they do not create merge, spend, publishing or data-integrity risk.
4. Product recommendations and editorial ordering stay independent from affiliate commission.
5. Do not merge production-impacting changes, publish social content, activate merchant offers or create new paid generation spend without the relevant approval gate.
6. Keep exact product identity, concentration, volume and imagery provenance verifiable.

## Priority board

### P0 — Launch readiness and publish-ready content

**Objective:** enter 2026-09-26 with a compact, high-quality buffer rather than a large unfinished bank.

Current state:
- Naxos campaign final: approved.
- Bois Impérial final: approved.
- Sillage vs. Haltbarkeit: final review render produced, operator review pending.
- Imagination / Marwa / Hectic: 15-second motion-graphics review render produced from existing verified assets, operator review pending.
- Dupe ≠ Dupe: 15-second relationship-education motion-graphics review render produced from existing verified assets, operator review pending.
- 3 Bürodüfte / 3 Typen: 15-second occasion/advisor motion-graphics review render produced from existing verified assets, operator review pending.
- First `I want to smell...` static (Naxos): 4:5 and 9:16 review assets produced, operator review pending.
- Existing script/preview bank remains available for later conversion.
- No social publishing action has been taken from this roadmap.

Next:
- fixed launch order starts with Naxos campaign final, then Bois Impérial final;
- operator visual review remains required for Sillage, Imagination/Marwa/Hectic, Dupe ≠ Dupe, 3 Bürodüfte / 3 Typen and the Naxos static;
- only after review, classify pending assets as publish-ready or revise;
- preserve roughly 30% of future slots for real audience response after launch.

### P1 — Website premium visual layer

**Objective:** make the existing discovery/advisor product feel like a premium fragrance platform without turning it into a single-product shop.

Draft branch:
- `dufynd-visual-refresh-20260923`
- Draft PR #46 against `scentai-mvp`

Implemented:
- editorial premium homepage hero;
- warmer DUFYND product cards;
- premium fragrance-detail hero;
- visual accord system;
- improved top/heart/base note presentation;
- upgraded comparison discovery and comparison detail experience.

QA:
- latest full CI green;
- production build passes;
- no catalog ranking, affiliate recommendation logic, legal copy, analytics contract or product data changed.

Gate:
- no merge/deploy before operator visual review and final mobile smoke.

### P2 — Distribution system

**Objective:** one strong master creative, then platform-appropriate reuse.

Channels:
- TikTok
- Instagram
- YouTube

Rules:
- do not build three separate production pipelines;
- adapt hook/caption/title per platform;
- measure qualified landing sessions, advisor starts, saves/shares and downstream merchant clickouts;
- do not judge a format from one post when no quality/compliance issue exists.

### P3 — Catalog expansion

**Objective:** unlock the researched Next 10 rather than expanding the research queue prematurely.

Current state:
- 32 products in the current catalog.
- Next 10 research: 10/10 source-researched.
- Next 10 catalog-ready: 0/10 by design.

Primary blockers:
- canonical GTIN/feed matching;
- verified affiliate offer availability;
- approved exact-variant imagery;
- remaining candidate-specific source conflicts.

Decision:
- do not spend effort researching another broad batch until these gates are materially improved.

### P4 — Affiliate and merchant activation

**Objective:** increase real merchant coverage without contaminating editorial selection.

Immediate operator maintenance gate:
- Awin/CJ publisher properties were originally created under the historical SCENTAI public brand.
- DUFYND is now public and `dufynd.de` is live.
- Update network-facing property/website metadata in place to DUFYND; preserve all existing applications, approvals and account history.
- Checklist: `docs/dufynd_affiliate_rebrand_checklist_20260923.md`.
- Current status snapshot: `examples/retail/data/dufynd_affiliate_status_20260923.json`.

Current known state:
- Perfumetrader has merchant-level approval/tracking evidence.
- Product-level activation remains separately gated.
- top Parfümerie feed intake work exists in PR #43 and remains non-production.
- Perfumetrader product-data/feed/image request has been sent; response is still pending as of 2026-09-23.
- rejected and pending programs remain distinct states.

Next:
- keep feed/mapping work read-only until exact SKU/GTIN/deeplink/image checks pass;
- follow up with Perfumetrader if the external response remains absent;
- use audience/traffic evidence after launch to improve future affiliate applications.

### P5 — Learning loop

**Objective:** turn launch data into decisions rather than reacting to vanity metrics.

Fixed approved launch order:
1. Naxos campaign final.
2. Bois Impérial final.
3. Review-pending assets follow only after explicit creative approval.

Measurement readiness:
- Live Supabase analytics is active and already recording first-party events.
- Pre-launch baseline: `examples/retail/data/dufynd_prelaunch_analytics_baseline_20260923.json`.
- Launch tracking links: `examples/retail/data/dufynd_launch_tracking_links_20260923.json`.
- Review cadence / decision logic: `docs/dufynd_launch_measurement_playbook_20260923.md`.
- Acquisition/content funnel views are already deployed; no analytics migration is currently required before the 2026-09-26 soft launch.

Weekly review after launch:
- qualified DUFYND landing sessions;
- advisor starts;
- comparison engagement;
- saves/shares where available;
- merchant clickouts as downstream signal;
- creative completion/retention metrics where platform data is available.

Scale rule:
- identify 3–5 repeatable creative formats;
- prefer at least three comparable tests before materially changing the mix;
- stop or revise immediately when product accuracy, compliance or visual quality is weak.

## Parallel work map

| Track | Can run now? | Current blocker | Approval gate |
| --- | --- | --- | --- |
| Content editing from existing assets | Yes | operator review at final stage | publish |
| New paid AI video/voice generation | No by default | spend discipline | explicit spend approval |
| Website visual refinement in draft PR | Yes | operator visual review | merge/deploy |
| Feed/GTIN research | Yes | external/feed evidence | offer activation |
| New merchant offer activation | No | exact mapping + QA | operator approval |
| Social publishing | No | launch/rebrand hold + review | operator approval |
| Next-10 source research | Mostly complete | feed/images/offers | publication gate |
| New broad catalog research wave | Low priority | current Next-10 not unlocked | roadmap reprioritization |

## Current operator review queue

1. Sillage vs. Haltbarkeit 15-second final review render.
2. Imagination / Marwa / Hectic 15-second motion-graphics review render.
3. Dupe ≠ Dupe 15-second relationship-education review render.
4. 3 Bürodüfte / 3 Typen 15-second advisor-format review render.
5. Naxos `I want to smell...` 4:5 and 9:16 static concept.
6. Website visual refresh PR #46 as a whole.

Until those reviews happen, independent commercial, QA and documentation work can continue, but none of the review-pending items above may be silently promoted to production.


## Operator review decisions — 2026-09-23

- Sillage vs. Haltbarkeit: 5/10, reject as publish candidate; rebuild from a proven viral-example structure.
- Imagination / Marwa / Hectic: 7/10; keep as education only after sound redesign.
- Dupe ≠ Dupe: 7/10; keep as education only after sound redesign.
- 3 Bürodüfte / 3 Typen: 7/10; keep as education only after sound redesign.
- I want to smell Naxos: rebuild as a multi-fragrance desire post with at least two fragrances; remove the black description box.
- Website visual refresh: 8/10 direction approved; next iteration should add stronger 3D/product dynamics.

### New production standards
- Naxos final remains the minimum premium-short quality floor.
- Educational content must first work as a viral/social-native visual; teaching can live in concise on-screen text and the caption.
- Homemade synthetic music beds/generic SFX are banned from final DUFYND shorts.
- Preferred Foley is sparse and physically motivated: atomizer spray, camera shutter, page flip, or a natural transition whoosh.


## Revision work started after operator review
- New Sillage visual master produced from the viral-example workflow: macro spray -> masculine airborne trail -> male wrist macro -> clean end statement. Audio intentionally withheld pending visual approval.
- New I want to smell static produced as a three-fragrance 4:5 mood post (Naxos / Althaïr / Stronger With You Intensely) with no black description box.
- Website visual branch extended with a lightweight 3D product-depth system: floating bottle motion, depth shadows and restrained perspective response on hero/detail/product cards.


## Director/DP production update
- Permanent DUFYND decision lens now covers director, cinematographer, creative director, entrepreneur, content creator, sales strategist and mentor roles.
- Sillage V3 Director's Cut created under the new shot-prompting standard. Shot A uses successful perfume-aerosol motion; Shot B uses a controlled cinematic hold because Seedance motion reduced particle readability; Shot C restores desire with a premium product hero.
- I want to smell addictive V2 rebuilt with a generated organic-luxury set plate and transparent cutouts extracted from the exact existing DUFYND product assets to preserve product identity.
