# Phase 2D.1: exact purchase freshness

## Problem and recovery

The Perfumetrader 1 Million EDT 100 ml observation from 2026-09-29 12:04:36 UTC expired at 2026-10-02 12:04:36 UTC. The customer-facing 72-hour gate correctly excluded it. Production smoke consequently returned 17/18. A previous AI watchlist consumed budget and dumped queue context without obtaining a current merchant observation.

PR #620 recovered the unchanged exact offer from direct no-cache merchant evidence. Only its verification timestamp changed. The GTIN, merchant article, price, shipping, stock, affiliate route, ranking and catalog remained unchanged. Dependent generated status snapshots were regenerated to satisfy existing consistency checks. Production smoke and post-merge CI returned green.

## Contract and permission boundary

`purchase_destination_freshness_audit@1` is compiled and initially acceptance-only. Admission requires a completed real merchant verification, matching report hash, stored evidence, done task and released lease. The only configured target is `perfumetrader-rabanne-1-million-edt-100`, bound to the current repository offer contract and canonical GTIN 3349666007921, EDT 100 ml, article 16978322. A new merchant or variant requires a reviewed migration through a PR to scentai-mvp.

Capabilities: commerce.read, commerce.verify_exact, commerce.evidence.write, supabase.task_state, supabase.execution_state. Worker tools remain the two existing fenced checkpoint/finish RPCs. No arbitrary URL, HTTP headers, HTML, shell, instructions or success claim may be supplied as worker tool arguments. Actual HTTP responses come from pg_net-owned requests to two fixed HTTPS merchant URLs. No Awin click is generated. Route validation compares the exact approved publisher, advertiser, clickref and merchant target; it does not claim a new network redirect verification.

Logical phases are separate: checkpoint starts/consumes the exact merchant audit; finish validates its hash and persists evidence. Only a `safe_evidence_refresh` report advances the verification date. Offer/business fields never change in the database or repository. The existing API reads this evidence using its existing backend Supabase credential and applies the date only when every canonical business field matches. It opens no new public HTTP route. Missing credentials, outages, expired evidence, revoked certification or changed contracts cannot manufacture freshness. Reads are cached for at most 60 seconds; merchant verification is not performed in user requests.

The trusted compiled worker still has a service-role credential. This is application authorization, not a sandbox for untrusted code. Introducing arbitrary agents requires a credential broker first. Tables have RLS, no public policies, and service-role-only RPC grants.

## Pre-expiry and recovery

The existing two-minute supervisor checks the target's due time: last_verified_at + 72h - safety_window_hours. No existing safety margin was found. Default 24h gives a full day for retry/review before exclusion; it is configurable from 1 through 48h. The customer-facing 72h gate is unchanged. Dedupe identity includes target, evidence generation and retry generation.

One due event enters the existing inbox, one existing external wait becomes satisfied, capability selection persists one compact immutable task packet, and the existing deterministic watchdog dispatches the compiled handler. It needs no chat, paid model, new daemon, second queue or GitHub dispatch token. pg_net requests and execution checkpoints survive worker/chat loss. The existing claim/resource lock and rotating lease fence prevent concurrent mutation. A stale worker cannot submit progress or finish. Request responses must be fresh, bounded and associated with the execution's persisted request IDs.

The packet contains only the exact canonical identity, offer contract, old evidence date, expiry, fixed verification contract and allowed evidence mutation. It stays under the existing 8192-byte limit. HTTP bodies and cookies never enter packets or durable reports.

## Deterministic decision rules

| Finding | Result |
|---|---|
| Exact unchanged title, SKU, GTIN, price, shipping, InStock and approved route | Persist evidence and advance verification time |
| Price/shipping change | Persist evidence, block for commerce review; no price overwrite |
| OOS, unknown stock, size/concentration/refill/SKU/GTIN mismatch | Persist evidence, fail closed; no freshness advance |
| Changed tracking structure or merchant destination | Persist evidence, fail closed; no new route |
| HTTP failure, oversized response, timeout, missing/stale response | No freshness advance; technical retry after six hours |

A material finding pauses further automatic refresh for that contract. It does not invent a human approval or alter business strategy. The existing task records the precise reason. Only a genuine business decision requires the owner; parser/transport failures remain technical work.

## Acceptance honesty

Production evidence is newly refreshed, so its normal pre-expiry boundary is two days away. Initial certification uses an explicitly labelled `initial_certification` event, rather than falsifying the evidence clock. The real free acceptance exercises the same event/wait/capability/packet/checkpoint/evidence/completion path and makes real merchant requests. Deterministic PostgreSQL tests exercise the actual approaching-expiry scheduler and replay the historical 72h incident: the old observation would have emitted its wake on 2026-10-01 12:04:36 UTC, one day before the production exclusion. Initial-certification acceptance must not be described as a real-clock approaching-expiry event.

## Optimization candidates and next priority

| Candidate | Problem / cause | Automation / benefit | Risk | Priority |
|---|---|---|---|---|
| PURCHASE_PRE_EXPIRY | Freshness detected only after production exclusion; prior watchlist required paid context | Implemented deterministic wake, exact audit, evidence consumer; removes recurring timestamp/merchant checks for this target | Fail closed on changed commerce state; one exact target only | P0 |
| PURCHASE_COVERAGE | Other merchants still use static evidence and different parsers | Certify one merchant/target at a time through exact contracts; reuse scheduler | Wrong variant or feed identity | P1 |
| POST_MERGE_VERIFIER | Repeated manual CI/deploy/smoke checks | Reuse registered GitHub observers and exact SHA evidence; avoid duplicate API polling | Deployment identity requires autonomous Render credential | P1 |
| CREDENTIAL_BACKOFF | Four missing credentials are retried despite blocked_configuration | Existing health/backoff retained; provision read-only autonomous access once | Credential leakage or unintended scope | P1 |
| DEPENDENCY_READINESS | Repeated readiness checks | Already performed by external-event dependency reevaluation; extend evidence only where a measured gap exists | False dependency completion | P2 |
| STATE_SNAPSHOT | Manual state audits and stale acceptance receipts | Existing certified state audit and receipt projection cover this | No repair authority | Covered |

No additional parallel handler is introduced. Next highest-impact general verification handler is post-merge verification, after its evidence sources and credential boundary are available.
