# Phase 2C.1: certified capabilities and compact packets

The Phase 2B/2C execution ledger, inbox, resource locks, leases and Actions runner
remain the execution plane. `dufynd_handler_contracts` replaces the prior embedded
`durability_probe` allowlist; it is contract metadata, not another task registry,
queue or orchestrator. Exactly that existing handler/version is explicitly seeded.
Unregistered legacy handlers, arbitrary commands and all paid handlers stay closed.

A contract declares ID/version, capabilities, required capabilities, allowed
scopes/resources/tools, forbidden actions, risk/cost/durability classes,
verification policy, retry/parallel support and optional approval class. Selection
uses exact payload kind, known capabilities and subset matching, then scope,
resource, dependency, approval, risk and cost filters. Stable C-collation ascending
ID/version is the tie rule. Only compiled, tested handler versions are eligible;
a database row alone cannot enable arbitrary code. Sensitive capabilities remain
explicitly excluded from this free-only phase. Existing atomic claims enforce
resource collision, lease/fencing, budget and human policy after matching.

The effective capabilities are the union of task requirements and the handler's
minimum requirements, not all capabilities the handler may have. Additional
harmless certification does not widen the worker packet. The probe's worker RPC
facade exposes only checkpoint and finish with fixed task/execution/worker/fence
identity. SQL rechecks current certification at dispatch, checkpoint, completion
and supervisor recovery. Revocation parks recovery with an explicit health finding;
it does not misclassify a technical block as an owner decision.

## Packet v1

Each new execution persists its packet and SHA-256 before dispatch. The packet
contains task/execution identity, fixed bounded goal, exact scope, effective
capabilities, exact resources, tools, forbidden actions, relevant dependency IDs
and statuses, initial checkpoint, relevant external event ID, expected arithmetic
output, verification contract, bounded payload, retry context, idempotency identity,
initial fence and a minimal contract snapshot. Maximum JSON size is 8192 bytes.
No free-form task instruction/evidence prose, mail body, complete chat history or
project dump is included. Missing/large/uncertified packets fail closed.

The packet, payload, identity, resources and hash are immutable even for supervisor
updates. Retry uses the identical packet/hash while reading the current checkpoint,
attempt and rotated fence from the existing execution row. The initial fence is
provenance only. Changed work requires an explicit new execution/packet; no in-flight
packet editing or silent version update API exists. Historical completed executions
remain historical without invented certification.

## Boundary and verification

This is a trusted deterministic runner, not a sandbox for arbitrary third-party
code. Its pre-existing Supabase service-role credential remains in the isolated
Actions job. The task-bound facade and fenced SQL provide application authorization;
external untrusted workers would require task-scoped credentials before admission.
No connector session credentials are exported and no AI worker is enabled.

Python tests exercise packet-only resume without chat, forbidden/ungranted tools,
identity/resource override denial and missing legacy packets. Real PostgreSQL tests
exercise matching, missing/unknown/sensitive capabilities, harmless extra contract
capability, revocation, scope/resources, immutable packet and fence rotation. Existing
contention/observer/recovery regressions continue against the new migration.
Live acceptance must separately record matched handler, packet hash/version,
execution/run, verified output, evidence, release and unchanged model spend. Passing
CI alone is not a live acceptance receipt.

## OPTIMIZATION_CANDIDATE

| Problem | Cause | Automation | Benefit | Risk | Priority |
| --- | --- | --- | --- | --- | --- |
| Acceptance stayed `armed` after successful Phase 2C | Final ledger proof not projected into status key | Deterministic acceptance receipt projection from exact execution/event/run | Fewer stale handoffs | Avoid declaring success from runner exit alone | P1 |
| Watchdog can recover only the arithmetic probe | Small deliberately certified handler set | Phase 2D audit and certify bounded read-only health/CI checks | Real operational work independent of chat | Exact pinned identity and no arbitrary shell | P1 |
| Large accumulated continuity checkpoint | Historical/business context shares one document | Project a compact phase-specific continuation packet | Lower context drift and token cost | Preserve authoritative source pointers | P2 |
| External sources poll despite absent credentials | Configuration blockers remain enabled | Deterministic configuration health with backoff / credential activation event | Fewer fruitless polls | Never fabricate healthy state | P2 |
| Arbitrary external agents would inherit broad credentials | Current trusted runner credential boundary | Task-scoped authenticated RPC broker before untrusted workers | Credential least privilege | Requires separate security design | P1 before external workers |

Virtual offices, permanent agent fleets, self-modification, AI model routing and
complex department hierarchies remain optimization candidates outside current P0.
