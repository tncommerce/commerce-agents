# DUFYND Profitable Organic Growth — Phase 1

Owner directive received 2026-10-03. Live evidence wins over older launch plans.
Working branch `scentai-mvp`; `main`, PR #1 and PR #598 remain untouched.
No paid generation, new subscriptions, public publishing or external messages.

## Verified baseline

At intake, GitHub/Render API matched `3e20cc8e770b51ddadde4889ec50ac38ebf3f7c6`
(PR #644). CI passed; production smoke 18/18. Owner Control Room HTML/snapshot
were accepted live. TECH lease is released; no nonterminal worker execution was
observed. Only PR #1 and #598 were open. This Growth change adds a separate report
and documentation, not writes to supervisor, observer, budget, queue, lease,
affiliate mappings, content production or storefront ownership areas.

The API's internal catalog has 122 products; the public fragrance list returned
34. There are 53 stored merchant offers; four pass static freshness/eligibility,
but three of those products are not publicly activated. Live candidate offer
endpoints below are the authoritative test, not the stored offer count.

The seven-day database extract ending 2026-10-03 17:37:23 UTC has 240 events.
The new report observes 146 landing sessions, 63 product-interest events and one
merchant-clickout event. All 210 relevant funnel events lack complete content
attribution; there are zero observed tagged social cohorts and zero observed
qualified tagged social visits. This does NOT mean no real visitor has interest.
Unmarked QA, owner activity and bots are not separated, so these counts cannot
be presented as validated customer demand or a conversion baseline.

Existing content inventory: 11 asset rows, 18 board items and 16 library formats.
`dufynd_content_performance` has zero rows; `dufynd_content_funnel_v1` has zero
rows. No measured affiliate conversions or revenue are present in that
performance source. They remain unknown, not zero revenue.

## Gap analysis

| Area | EXISTS | PARTIAL | MISSING | BLOCKED / boundary |
| --- | --- | --- | --- | --- |
| Attribution | Sanitized channel/campaign/content IDs, hashed API sessions, tab-scoped persistence, landing/navigation propagation, analytics events, acquisition/product/content funnel views, campaign-link builder | Product clickout records preserve content IDs; Awin merchant-discovery dynamically forwards clickref; product offers keep their static affiliate target | Attributed live cohorts; validated per-post identity mapping; network transaction reconciliation; QA/owner exclusion evidence | Product-offer dynamic clickref and CJ contract changes belong to the Affiliate/API handoff; no provider access or paid analytics inferred |
| Product readiness | 122 internal/34 public products, exact variant fields, guarded offers, 72h freshness, known-total ranking, disclosures | 1 Million public affiliate path currently eligible; other content-ready products have stale/missing offers | Small test group with fresh commerce AND per-revision asset/rights evidence AND attribution | PR #598 untouched; no product promotion, price/date bump, merchant requests or rights assumptions |
| Content MVP | 16 formats, idea/board/assets, scripts/packs, existing locked masters; versioned factory plan | Existing QA references and owner acceptance cover specific masters; platform performance schema exists | Enforced independent revision-bound maker/checker, complete post metadata and actual measurement rows, bounded production loop | No paid generation or automatic publishing; CONTENT/JARVIS implementation handoffs only |
| Conversion | Product pages, comparison/entry pages, offer section/impression events, shipping/total ranking, mobile full-width merchant CTA, affiliate/trust copy | Mobile layout replay passes; live offer API is healthy; reference price and current offer are visibly different | Proven tagged journey to attributed transaction; sufficient clean baseline for experiments | Browser direct API transport timed out in this environment; do not infer a production outage or claim full browser E2E success |

## Small test group

| Product | Live observation | Phase-1 use | Remaining gate |
| --- | --- | --- | --- |
| Rabanne 1 Million EDT 100 ml, `SC-RABANNE-1-MILLION-EDT-100`, GTIN 3349666007921 | Public; one eligible Perfumetrader/Awin offer, item €71.90 + €4.99 shipping = €76.89, in stock, checked 2026-10-02 13:38 UTC | First instrumented single-product test using existing `one_million_example61_01` master; direct product landing `/duft/rabanne-1-million` | Per-platform IDs/actual posting evidence, campaign assignment, network clickref reconciliation and exact reused asset/audio rights review |
| Bois Impérial EDP 100 ml, `SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100` | Public; live offers currently empty; existing locked master | Conditional second product / office-use story after commerce readiness | Fresh exact-variant offer and rights/QA evidence; no stale merchant/date refresh by this strand |
| Xerjoff Naxos EDP 100 ml, `SC-XERJOFF-NAXOS-100` | Public; live offers currently empty; existing locked master | Conditional third product / single-product or occasion story | Fresh valid commerce path; coordinate Affiliate owner, never merge or change PR #598 |

Lancôme La Vie est Belle EDP 100 ml is a useful later candidate with licensed
image evidence, but its live offer list is also empty. YSL Libre EDP 90 ml is
currently publication-gated (offer endpoint 404), despite a stored eligible
Notino offer. Do not call either immediately revenue-ready. Product identity,
current offer and page readiness alone never clear content rights or publishing.
Reverify offers at execution time; this table is a dated observation.

## Minimal implementation sequence and handoffs

| Task | Responsible surface | Business effect / hypothesis | Acceptance | Cost / boundary |
| --- | --- | --- | --- | --- |
| G0-01 Read-only funnel evidence (implemented here) | Separate Growth report | Makes attribution failures visible before optimizing fabricated ROI | Bounded exact-count GETs, explicit window/cohort qualification, no session IDs in output, unknown revenue, QA exclusions, tests | Existing Python/httpx; no schema or scheduled job |
| G0-02 Assign and retain per-platform links | CONTENT + Growth operating handoff | Direct product intent should reduce navigation loss; distinct links identify which post produces interest | Existing link builder; stable content ID + platform + campaign + actual post ID; local intercepted landing → product → clickout test; no live click | Prepare internally; changing published bios/posts needs Owner publishing approval |
| G0-03 Product-level affiliate correlation | AFFILIATE/API handoff | Connects clickouts to settled commission per content instead of general channel estimates | Awin allowlisted-host URL tests preserve publisher, advertiser, encoded destination; validated clickref contract; CJ sub-ID independently verified; unknown networks fail closed; no live merchant test-click | No mapping/PR #598 changes here; provider settings/access require owner when necessary |
| G0-04 Verified transaction evidence | AFFILIATE/Growth handoff | Enables revenue per content and per 1,000 qualified visits | Initial read-only export/import design: network transaction ID, clickref, currency, commission vs basket value, status, event time, settlement time, refund/dedup/source provenance; reconcile coverage/window before rates | Use existing performance metadata or a narrow ledger only for demonstrated gaps; no invented conversions |
| G1-01 Eligible-offer shortlist | AFFILIATE handoff | Converts already prepared assets into purchasable journeys with less owner effort | Exact concentration/size/GTIN, current price/stock/shipping, validated partner path, truthful timestamps; known total first; commission only equivalent offers | Refresh only with evidence; reuse existing verification targets |
| G1-02 Product landing and total-price clarity | TECH storefront handoff | Reduces generic-link navigation loss and price surprise before clickout | Compare direct product entry vs generic advisor entry; show verified delivered total explicitly including shipping; stale offer must not become hero price | Reuse live offer payload; no commission-based recommendation or invented price |
| G1-03 Mobile merchant target | TECH storefront handoff | Larger finger target and shorter nearby copy may reduce missed clicks and uncertainty | Layout replay observed CTA 264×39.5px at 390px viewport; test ≥44px target, total/variant/freshness/disclosure visible; measure offer-view → clickout sessions | Small functional hypothesis, not redesign; owner/QA traffic separated first |
| G2-01 Minimal content brief/checker contracts | CONTENT/JARVIS handoff | Reuses masters/formats and reduces repeat owner review | Immutable revision hash; different maker/checker identities; hard fails; bounded revisions; READY FOR OWNER APPROVAL only | See `content-factory-v1-plan.md`; no worker/queue changes here |

Initial priority: measurement coverage + first exact product test; then verified
commission reconciliation; then one focused conversion experiment; scale only
when there is repeatable evidence. No universal product score, paid stack, large
catalogue redesign, membership, community, mass SEO or Level-4 autonomy.

## KPI definitions and evidence rules

- Social views/impressions/reach, retention/completion, saves/shares and site
  clicks come from dated platform evidence. Unknown fields stay null.
- Social → DUFYND CTR requires compatible platform/link-click denominator and
  time window. Do not divide anonymous sessions by unrelated all-platform views.
- Sessions mean observed anonymous API analytics sessions, not unique people.
  Mark QA/test prefixes; owner/bot exclusion is not currently established.
- Product views are explicit product-interest events; avoid reporting these as
  unique product visitors. Existing product-funnel reports can provide session
  variants once sources/windows are aligned.
- Qualified DUFYND visits: tagged social landing followed by a product-interest
  event in the same session/content/campaign/platform cohort, within the window.
  This is an operational engagement proxy, not consent to identify a person.
- Qualified clickout rate = qualified sessions with subsequent merchant clickout
  / qualified sessions. Raw event clickout counts are shown separately.
- Affiliate conversion means a verified attributed network transaction, not a
  clickout. Deduplicate transactions and preserve pending/approved/declined/
  refunded status. Revenue means DUFYND commission, not merchant basket value.
- Revenue per 1,000 qualified visits = attributed settled commission / compatible
  qualified visits × 1,000. Revenue per content piece/product uses the same
  verified cohort, period and currency. Both remain unknown until evidence exists.
- Content pieces count unique approved/published creative IDs rather than three
  platform adaptations as three newly produced masters. Measure owner minutes
  and production cost explicitly; do not infer zero cost from missing records.
- Store hypothesis, format, hook, opening visual, length, exact product/category,
  platform, CTA, posting time and revision evidence in existing asset/performance
  metadata. Use `dufynd-growth-content-brief.template.json` as an internal, non-ready example
  for existing metadata; it grants no publication and creates no job. Empty hard
  failures do not imply completed QA. Retain measured-at/source/sample size and
  uncertainty. Conflicting
  snapshots, currencies or refunds cannot be silently averaged or summed.

The reporter's configurable sample threshold defaults to 30 qualified sessions;
it is a guardrail, not a significance test. No automated growth decision follows
from passing that threshold. Untagged/unmarked traffic and incomplete ingestion
remain explicit limitations, even when the database extract is complete.

## Running the safe foundation

From repository root (existing server-only key in environment):

```sh
python -m scripts.report_dufynd_profitable_growth --days 7
```

Offline projected event arrays are supported with `--input`; their extraction
coverage remains unknown. Defaults are at most 10,000 events, bounded to 50,000,
fixed project and allowlisted columns, exact-count pagination and no redirects.
The report emits aggregated IDs/counts only, never raw session identifiers,
credentials, click URLs, search text or visitor profiles. Source failure is an
error, not a successful zero-valued report. There is no public route, mutation,
new schema, external publishing, provider call or schedule.

## Validation scope

11 meaningful tests cover cohort isolation, event ordering, duplicate suppression,
missing sales evidence, incomplete/sample gates, QA/window exclusions, fixed
GET-only projections, truncation and redirect failure. The report was replayed
against the current 240-row projected seven-day database extract, with exact
count agreement and no credentials/PIDs in the persisted report documentation.

At 390px the live product page renders without horizontal overflow. Browser API
requests timed out through the execution proxy; direct offer API GETs succeeded.
For offer-layout inspection, the browser used the exact live-read offer response
and intercepted session/analytics writes. This confirmed variant/shipping/trust
copy, CTA query attribution and layout; no merchant link was opened and no fake
analytics event was sent. This is intentionally not claimed as a completed live
transaction or unconstrained browser network acceptance.
