# Content Factory V1: implementation plan

Owner directives: [Control Room](jarvis-control-room-v1.md) and
[Growth order](dufynd-growth-directive.md). Publishing remains owner-controlled.

## P0 acceptance evidence — 2026-10-03, 19:18 Europe/Berlin

PR #643 is merged into `scentai-mvp`, commit
`0fb5f17c56c491e538d1734cb2e7ca4eddf5f5f1`. Required CI, including PostgreSQL
session/privilege tests, passed. The existing Render API is live on this commit.
60 focused read/auth tests passed. Desktop/mobile browser checks used real source
projections; no JS errors or horizontal overflow; read failure showed an explicit
unavailable warning. Production smoke passed 18/18 after the code merge.

The owner confirmed their login. The database shows one newly active owner
session. Render recorded the protected HTML at 17:17:44 UTC and live snapshot at
17:17:46 UTC, both HTTP 200. Anonymous reads return 401, forged cookies redirect
to login, and private responses are no-store. The final configuration deployment
is live; API health passes. This establishes authenticated endpoint acceptance;
it does not claim a screenshot inspection of the owner's private browser.

At 17:18 UTC the sources showed zero nonterminal executions, zero working tasks,
one task human gate and 15 waiting-external tasks. The existing pilot budget has
cap $2.50, recorded spend $2.5046854, remaining $0 and `can_run=false`. These are
observations, not a budget change or permission to restart paid work. The small
historical overage remains visible rather than being rounded away in evidence.
Provider/observer health and checkpoints remain subject to freshness labels.

## G0 first: audit the existing attribution path

The current API already accepts sanitized `content_id`, `campaign_id`,
`acquisition_source`, product and anonymous hashed session identifiers in
`analytics.py`. Product clickouts in `main.py` pass these identifiers to the
merchant event recorder. Merchant-discovery clickouts choose affiliate clickref
from content, campaign or source; product-offer clickouts currently use their
existing offer target without passing this dynamic clickref. That path needs a
network-specific audit before content-to-conversion linkage is claimed. `MerchantClickTracker` records offer, product, merchant, network and
time in a local JSONL file. Reuse these contracts; do not create a second tracker.

Next safe implementation: inspect the browser journey, current database columns,
existing reports and persistence configuration. Verify that a tagged landing
retains attribution through product interest and clickout. Test redirect URL
construction locally with a stub; do not make a live merchant click or purchase.
Live `scentai_analytics_events` already contains the content/campaign/source
columns; no duplicate schema is needed. Check whether local fallback/clickout
records survive deploys before treating metrics as complete. State missing attribution and reporting coverage explicitly.

Produce one bounded internal report of visits, product interest and clickouts
by existing identifiers, with time window, source completeness and null unknown
conversions/revenue. Platform/format/hook mapping should come from an authoritative
content registry; never infer it from ad hoc URL strings. Add fields/schema only
for an observed gap. No new paid service, frontend write controls or public data.

## G1: measured conversion improvements

Use G0 evidence to prioritize CTA, mobile journey, offer freshness, tracking and
merchant ranking. Validate total price, shipping, availability and merchant
quality; a higher commission must not choose a worse customer offer. Improvements
need a baseline, outcome and cost, not an arbitrary universal growth score.

## G2: smallest factory foundation

Reuse the existing task, durable execution and inbox contracts. Audit existing
content idea/job/asset tables and builder scripts before adding contracts.
Keep specialist role and content workflow stage separate from runtime worker
type and operational task/lease status. No new queue infrastructure by default.

1. Define a versioned content brief: stable content/campaign IDs, product ID and
   exact variant/concentration/size, merchant/offer, platform/format/hook,
   objective, audience, measurement plan and approved cost ceiling (zero while
   paid execution is disabled).
2. Bind immutable draft/asset revisions to hashes and provenance. Research,
   product truth and rights evidence remain separate typed references. Avoid
   copying credentials, full raw task payloads or private provider metadata.
3. Route plan/research/produce work only to existing, approved capabilities.
   Unsupported production remains blocked; draft plans are not completed assets.
4. An independent critic/verifier must review the exact revision. Enforce maker
   and checker identity separation in orchestration, including reused identities
   across attempts. Product/bottle/variant mismatches, unsupported facts, unclear
   rights, wrong affiliate destination or missing gates always fail, regardless
   of average quality scores.
5. Failure creates a bounded revision, invalidates old approvals and returns to
   independent review. Default maximum two revision rounds per brief; unresolved
   failures go to the owner. Paid attempts require a separately approved budget.
6. Only all mandatory checks on the current revision can produce
   `READY FOR OWNER APPROVAL`. Editing draft, assets, rights, product or destination
   invalidates readiness. No publisher handler, schedule or automatic publication
   is enabled in this phase. Owner approval is distinct from a publish command.
7. Add an allowlisted read-only content projection to the existing dashboard only
   after real content records exist. Owner review shows draft/asset, exact product,
   critic results, rights/affiliate evidence, costs and revision lineage.

Acceptance tests must cover self-approval denial, stale revision rejection,
hard-fail precedence, bounded revision retries, duplicate dispatch, missing
rights/affiliate evidence, and absence of publishing. A zero-cost fixture flow
can validate orchestration without producing paid media or changing a live queue.

Later G3 experiments, G4 evidence-backed learning, G5 revenue priorities and G6
publishing autonomy follow the Growth directive. Do not skip owner/security/spend
or publishing gates to make the pipeline appear autonomous.
