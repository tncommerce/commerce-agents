# Post-P0 mini-canary acceptance — 2026-10-04

## Live result

Run #47, GitHub 37188826814, **attempt 2**, completed with failure at
`scentai-mvp` commit `d647c5647525799f06a504715949c39dedcee00f`.
Attempt-2 artifact 11298440995 contains counted-terminal.json and both morning
report formats. Do not confuse it with attempt-1 artifact 11297543106.

Budget `jarvis_nightshift_mini_canary_20261004_002`: cap $0.08, max two paid
calls, spent $0, runs 0, remaining $0.08/two calls, no reservations or
settlements, reserved unsettled $0, provider_cost_unknown=false.
No new run, retry, budget change, approval change or task requeue was performed
in this investigation. Remaining approved capacity does not authorize a retry.

Attribution task was claimed then blocked with `counted_worker_failed_no_retry`;
its lease was released at 08:27:30.601742Z. Content remained ready/queued with
no active lease. Its stored prose belongs to Run #45, not a new maker output.
The saved terminal stop reason `unknown_provider_cost` conflicts with its own
empty, zero-cost counted ledger. The morning report also incorrectly marks
cost completeness false. These are diagnostic/reporting defects, not spend.

## Acceptance criteria

| # | Criterion | Result |
|---|---|---|
| 1 | Valid reservation before every paid call | No paid call; zero reservations. Execution path unexercised. |
| 2 | Exactly one dispatch per call | Zero dispatches; unexercised. |
| 3 | Clean settlement per call | Zero settlements; unexercised. |
| 4 | No unsettled reservations | PASS: zero. |
| 5 | provider_cost_unknown=false | PASS in live budget and counted ledger; historical stop reason is contradictory. |
| 6 | Budget <= $0.08 | PASS: $0. |
| 7 | <= two paid calls | PASS: zero. |
| 8 | No retries | No additional generation/retry in attempt 2 or this investigation. Attempt 1 failed budget resolution before generation. |
| 9 | No tools in paid request | No paid request. Fixed client exposes no tools. |
| 10 | No publishing | No publishing action performed. |
| 11 | No external messages | No external message action performed. |
| 12 | No TinyFish | No TinyFish action performed. |
| 13 | Evidence actually received by each maker | NONE: no paid maker dispatch for either task. Exact pre-count snapshot was not persisted by old code. |
| 14 | Boundary omissions | Original content pack reconstructs omissions of subtitles/social/readiness/index. Reconstruction is not proof of delivery. |
| 15 | Task relevance | Offline allowlists cover attribution path and content families; live maker use untested. |
| 16 | Provenance/hashes complete | Offline packet tests verify hashes, ranges/projections and exclusions; actual delivered packet absent. |
| 17 | Better result than Run #45 | NOT PROVEN: attempt 2 produced no maker outputs. |

## Diagnosis limits and free fixes

The old catch records only exception class `BudgetGate`, discarding its reason,
phase, count and context hash. No worker failure run was recorded. Nightshift
then treats the missing run-cost evidence as unknown billing. Exact original
BudgetGate subtype cannot be recovered from available logs/artifacts; do not
assert token overflow, credential failure or reservation denial as established.
Pricing was still within its configured validity window at failure time. The
approval resolver had been corrected; no approval/budget modification is needed.
Token-count metadata HTTP activity cannot be excluded; zero **paid generation**
is proved by the reservation-first path and empty live ledger.

The fix persists exact task context before counting, preserves safe reason,
phase, returned count, prompt size, packet hash and GitHub execution identity.
Only exception type or a bounded identifier is logged, never arbitrary HTTP
error bodies. A failed worker records known zero cost only while no paid HTTP
request was attempted; after possible dispatch it retains unknown cost unless a
valid receipt yielded actual cost. Known-cost counted failures stop Nightshift
without retry or selecting the next task. Maker self-approval remains blocked.
Counted morning/terminal reports use reservation-ledger completeness separately
from execution success, retaining conflicting historical diagnostics explicitly.

Packer line groups now include their rendered line prefixes in the byte bound
and stop after four groups instead of filling remaining space with low-value
punctuation/ranges. Content prioritizes all three full hook/voiceover batches,
all subtitle openings/timing summaries and TikTok caption openings, voiceover
spec excerpts, strategy, quality-floor registry, pipeline and learning sources.
Media projections are explicitly partial (80-character openings, omitted middle
subtitle text/platform copy; guidance and notes bounded). Full audiovisual QC,
full captions/subtitles, readiness/index and later learning/checklist coverage
can still be missing. Byte bounds are not tokenizer proofs: the existing
count/margin gate is unchanged and still denies oversized input before spend.

## Comparison / independent check

Run #45 /37163023650 succeeded at
`11b882d89bf1fc313756c2325a42c944587f82e5`. Its stored attribution output reports
one truncated analytics.ts source; content reports only strategy/launch-assets
and cannot select three pilots. Those are historical maker statements, not
final acceptance. Attempt 2 cannot establish better navigation/offer/clickout
analysis, candidate ranking, supported claims or hallucination absence because
it has no new maker output. Independent acceptance remains **needs_more_evidence**,
with no paid checker, no final task/content approval and no automatic next task.

Observer Run #10 /37188527487 completed successfully at d647c564; no rerun was
started. Live Jarvis health was idle: inbox pending/processing/failed all zero,
ready_count=1 (content), waiting_human=1, waiting_external=15. Launch gates
content_attribution and launch_tracking remain pending; do not synthesize events
or click merchants to mark them passed.

**NO-GO for paid autonomy / another canary.** Free tests and PR/CI may proceed.
After merge stop before provider execution. The next business leverage is real
observed launch attribution evidence and no-spend pilot finalization planning;
next technical leverage is independently auditable context/maker/checker receipts.

## Exact live-task regression

The longer live content instruction changes excerpt ranking and packet size. A
post-merge offline reconstruction exposed that it could omit every learning
source despite shorter fixtures passing. The primary creative-learning library
now precedes optional buffer/secondary learning/readiness assets, alongside
quality-floor and pipeline evidence. A regression uses the exact live task ID,
title, instruction, domain and dependencies and requires all three batch scripts,
voiceover specs, subtitle/social projections and these essential source families.
This proves packet coverage offline, not paid Maker quality or full visual QC.
