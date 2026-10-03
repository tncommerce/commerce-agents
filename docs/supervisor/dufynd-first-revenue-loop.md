# First revenue loop: Rabanne 1 Million

## Verified state — 2026-10-03, database 18:05 / platforms 18:16 UTC

GitHub `scentai-mvp` and the existing Render API are live on
`4c64278836d1207ed71d103d8b854a45fbbd1ccc` (PR #645). Only PRs #1 and
#598 were open at the initial check; neither was modified. TECH lease is
released. This work adds Growth-only offline files, no runtime or database
mutation, infrastructure, paid generation, post editing or publishing.

Live `GET /api/merchant-offers/SC-RABANNE-1-MILLION-EDT-100` returns one
eligible Perfumetrader/Awin offer: EDT 100 ml, item €71.90, shipping €4.99,
total €76.89, in stock, certified 2026-10-02 13:38 UTC. Recheck before use;
this snapshot is not an evergreen price or availability promise.

| Evidence in retained analytics at verification | Observed | Limitation |
| --- | ---: | --- |
| 1 Million `fragrance_detail_view` | 3 events / 3 sessions | Untagged organic; human/Owner/QA origin not established |
| 1 Million `product_open` | 1 event / 1 session | Different event type, not an additional unique visitor claim |
| 1 Million `merchant_clickout` | 1 event / 1 session | 2026-10-01 19:00:29 UTC; no campaign or content ID |
| Clickout session with earlier landing and product interest | 1 | Same anonymous session; no proven social provenance |
| Content-tagged funnel view rows | 0 | No measurable content cohort yet |
| Content performance rows | 0 | No conversion/commission evidence in this source |
| Asset rows keyed to this exact content ID | 0 | Repo master exists; DB linkage still absent |

These are stored event observations, not verified customers or completed
orders. Do not backfill historical untagged events with guessed social IDs.
An empty performance table cannot prove that no orders exist at Awin.

## Binding and published-post evidence

`dufynd-first-revenue-loop.json` retains the existing master/content ID
`one_million_example61_01`, existing prepared campaign `launch01_high_end`,
exact product/offer identity, and Awin static clickref
`one_million_example61_01`. These identifiers are consistent with the existing
launch-links and affiliate-evidence files. The previous general brief's
example `launch01` is not evidence of an actual published campaign.

Public search and repo reads did not identify posts, but the existing Windsor
organic account connections do. A normal read without forced refresh returned
platform metadata fetched at 18:15:31 UTC and metrics at 18:16:26 UTC:

| Platform | Verified post ID | Posting time / actual destination evidence |
| --- | --- | --- |
| Instagram | `17936625063388741`, [Reel](https://www.instagram.com/reel/Dd4PqziqHde/) | 2026-09-29 17:02 UTC; caption points to Bio; current account website already `/duft/rabanne-1-million`, without tags |
| TikTok | `7691036431489305888` | Connector returns actual share URL in manifest; caption points to channel profile. Raw posting time `2026-09-29T19:09:26` has no timezone; profile destination unavailable |
| YouTube | `v8DlVXi-Fj8`, [video](https://www.youtube.com/watch?v=v8DlVXi-Fj8) | Public, 2026-09-29 16:00:58 UTC; description points to channel profile, no direct URL in description; current profile destination unavailable |

All three titles/captions identify Rabanne 1 Million. Their relation to the
existing master is supported by metadata and the prior Owner publication
report; exact byte/visual equivalence is not yet independently verified.
Persisted connector job IDs and fetch times distinguish observed posts from
prepared links. Instagram reports 177 views / reach 147; TikTok reach 221,
views and website clicks null. YouTube returns 471 + 46 views and 98 + 15
engaged views for Sept 29/30 only. Missing dates are not zeros. These are real
platform observations, not proof of traffic or revenue. No Awin connection
was present in the connected-source inventory.

**Next evidence handoff to Owner/CONTENT:** verify exact master and the
remaining current profile destinations; decide an actually clickable,
uniquely attributable placement for one proposed tracked product URL. A
shared Bio or channel-profile URL can measure campaign-link traffic but
cannot prove which reel/video produced it. Instagram's current Bio URL is
shared by other posts too, so attaching a creative ID there alone is not
proof of per-post attribution. Do not retrospectively assign its untagged
traffic to the 1 Million Reel. No external link has been changed.

Only after verification should CONTENT bind the existing asset record's
content ID and platform metadata using its established write path. This
Growth change does not write to its exclusive tables or manufacture READY
state. The free existing reporter and views can then read actual incoming
tagged visits; no new analytics service or schedule is required.

## One prepared conversion test

**Hypothesis:** enlarging the mobile merchant touch target reduces missed taps
and raises qualified merchant clickout rate. The actual Instagram destination
is already the product page, so the prepared finder link is not a valid live
control for a landing-navigation experiment.

**Only conversion change:** on the 1 Million product landing, mobile merchant
CTA minimum height 44 px, centered content. Baseline at viewport 390 px is
264 × 39.5 px, measured on the live page with an exact live-offer replay while
blocking all writes and outbound clickouts. Keep position, wording, offer,
shipping, price and creative unchanged. TECH handoff: scope the existing
`FragranceOffers` anchor and its preparing state to this product/surface below
640 px; use inline-flex centering and `min-height:44px`. Do not make a global
merchant CTA change. Verify ready/preparing states at 360/390/430 px, no
overflow or layout shift, unchanged attribution href, and no new API calls.
No TECH/runtime file is modified by this patch.

The manifest separately prepares platform-specific tracked links to the
unchanged product landing under campaign `one_million_loop01`. These are
attribution foundation, not an already-running conversion test. Establish a
clean tagged baseline first and obtain Owner approval for any external link
placement/change. No proposed URL is asserted to have been published.

**Measurement:** report ordered product-interest sessions / tagged landing
sessions, and ordered clickout sessions / qualified visits, within identical
fixed seven-day windows and platform strata. Existing reporter excludes
explicit `qa_`/`test_` cohorts and requires same-session, same-platform,
same-campaign, same-content order. At least 30 qualified visits per cohort
is an extraction/sample gate, not statistical significance. No tagged
baseline exists yet; the single untagged clickout is not a control rate.
Separate Owner/QA traffic before evaluating. If deployment is sequential
and not randomized, report descriptive observations, not causal uplift.

**Expected business impact:** fewer missed mobile taps should raise merchant
clickouts per qualified product visit; effect size is unknown.
No added operating cost. Commission uplift cannot yet be compared by test
variant: the product affiliate URL currently uses a shared static creative
clickref, not a forwarded campaign/platform reference. Changing that behavior
belongs to AFFILIATE/TECH and is not part of this patch.

## Minimal Maker/Checker handoff

`scripts/check_dufynd_content_review.py` validates an offline review package.
It checks distinct maker/checker identities, SHA-256-bound package revision,
asset byte digest presence, all 15 mandatory checks with evidence references,
empty explicit hard-fail assessment and at most two revision rounds. Any
failed/unknown check blocks regardless of score or Owner flags. Revised asset,
caption, product or affiliate destination requires a fresh independent review.
The only successful stage is `READY_FOR_OWNER_APPROVAL`; the output always
sets publication authorization false. There is no publisher or provider call.

This is a contract validator, **not an authenticated approval authority**.
It cannot verify that claimed identities/evidence are genuine or that an
asset file still matches its recorded byte hash. CONTENT's existing executor
must derive identities from trusted worker execution records, compute actual
asset hashes and verify evidence before accepting a review. Do not wire an
untrusted CLI result directly to publishing. This handoff avoids changing
exclusive worker queues, Supervisor, Jarvis, Affiliate or TECH runtime.

Free operating sequence: freeze the exact asset, caption, platform/audio,
destination and rights evidence → maker records immutable package → a
different checker examines the actual deliverable and records each check →
run validator → revise on failure and re-review → Owner sees only evidenced
READY. Escalate unresolved failure after round two. Owner publication approval
is separate and must bind to the same frozen package.

The existing 1 Million visual QC is valuable partial evidence but does not
prove this complete independently authenticated chain: frozen byte hash,
checker execution identity, current platform audio rights and actual
published-link review are not supplied. **Operational readiness remains
blocked on these real reviews**, not on another generation pipeline.

## Last external evidence: affiliate conversion and commission

Request a free Awin export/read with clickref `one_million_example61_01` from
the AFFILIATE owner when available. Required evidence: network transaction
ID, merchant/program, transaction date, clickref, currency, order value,
commission value, status (pending/approved/declined/paid), update time and
source export reference. Keep order basket value separate from DUFYND
commission; deduplicate transaction ID, preserve corrections and reversals,
and never sum pending plus approved versions of the same transaction.

The shared creative clickref can support creative-level reconciliation once
actual transaction evidence exists. It cannot identify a platform/session or
experiment variant, and network-reported matching remains distinct from
first-party causality. Attribution window and delays must come from the
actual network report, not invented assumptions.

Until that export exists, conversions, pending/approved/settled commission,
revenue per content piece and revenue per 1,000 qualified visits stay null.
No synthetic production events, merchant clicks, orders or revenue were
created. The last supported endpoint is an untagged first-party merchant
clickout with an earlier landing and product view, not a proven paid sale.
