# Counted worker evidence, independent verification and reporting

The counted worker now selects an explicit public repository evidence profile from
task domain and intent. Attribution covers acquisition/session analytics, navigation,
offers, tracking/ingestion and correlation tests. Content covers all 15 pilot scripts,
voiceover specifications, subtitle/social drafts, pipeline/buffer state and current
quality/creative-learning rules. No live performance or video fidelity is inferred.

Sources have full-file SHA256 and excerpt line ranges or fixed JSON projection paths.
Missing, oversized, sensitive, symlinked and lower-priority sources are explicitly
listed. The serialized packet is capped at 30,000 bytes. Model token counting still
runs through the original contract: 8,192 input tokens, conservative margin/padding,
2,048 output cap and $0.036864 maximum reservation. A pack that cannot fit the existing
cost guard is rejected; no paid retry and no provider call builds the context.

Maker output remains blocked. A hashed handoff with original task, evidence/provenance,
result and bounded runtime metadata is persisted for an independent checker. The
checker contract supports accepted/verified, needs_more_evidence, rework_required,
waiting_external, waiting_human_input and blocked. A trusted host identity must differ
from the Maker; semantic checks cannot be replaced by the Maker's assertions. Tests
use offline checker doubles. There is intentionally no live paid checker adapter or
receipt-driven production completion endpoint yet. The next-safe-task helper is a
pure proposal, not a queue write. One bounded rework is supported; no automatic paid
retry. Publishing/owner approvals remain outside checker authority. A production
paid Checker and authenticated durable decision application require a separately
approved Canary and implementation review; no GO is implied by unit tests.

Cost reporting now accepts finite nonnegative decimal-text audited costs and uses
the authoritative reservation/settlement ledger for counted sessions. Session spend,
call receipts, unsettled reservation amount and cumulative remaining budget/runs are
separate fields. Historical `jarvis_activation_pilot_001` is never a counted ledger.
Terminal JSON and morning JSON/Markdown carry this evidence; unavailable evidence
stays incomplete rather than becoming a zero-cost claim.

## Private Observer failure and correction

Run 37171670435 used the initial-activation acceptance RPC after both observers were
already activated by run 37132941223. The live function deliberately raised
`private observer already activated`; this was an activation lifecycle mismatch,
not a parameter/signature or JSONB mismatch. Python accepted scheduled provenance
while SQL accepted only manual dispatch, a second drift now aligned for recurring
reads. Initial activation still requires manual dispatch.

The migration adds DB-selected recurring-read mode to the existing provenance/TTL
session. Exactly two active credentials choose recurring capture; zero chooses the
original activation path; partial activation is blocked. Capture and finalization
require activation to match the session mode plus fresh health and the existing
resource allowlist. Recurring finalize verifies four captures and the same idempotent
ack receipt, without modifying credentials. RPCs remain SECURITY INVOKER and
service-role-only. No secret or budget changes are part of this migration.
