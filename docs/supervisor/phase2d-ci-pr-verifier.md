# Phase 2D: exact CI/PR verification

The next free handler after purchase freshness is `ci_pr_verifier@1`. It removes repeated checks of whether a known merged PR and integration CI refer to the same exact commit. It reads existing registered GitHub observer snapshots; it makes no additional HTTP request, executes no repository command and performs no merge, deploy, repair, approval or commerce mutation.

## Admission and execution

The service-only `schedule_dufynd_ci_pr_verification(pr_number, ci_run_id, merge_sha, pr_head_sha, acceptance=false)` accepts one exact tuple for `tncommerce/commerce-agents`. Protected PRs 1 and 598 are rejected. It registers or reuses public `github_pr`/`github_ci` observers, stores the compact typed payload on the existing autonomy task and binds two existing external dependency waits. Repeating the tuple reuses the task. Fresh persisted matching source events may satisfy a newly bound waiter; no fabricated event or new polling loop is introduced.

Normal scheduling is denied until the fixed acceptance task has completed and passed service-only certification. Both actual GitHub events must satisfy the waits. The existing event processor prepares the immutable packet, and the watchdog executes the compiled SQL reader and finishes the fenced execution. The existing recovery path resumes the same packet if a worker disappears.

Capabilities: `github.ci.observe`, `github.read`, `supabase.execution_state`, `supabase.task_state`. Scope: `supervisor`. Resource: `db:ci-pr-verification`. Worker tools remain only the task-bound checkpoint and finish RPCs. Trusted service-role scheduling and the fixed SQL reader form the authorization boundary; these are not credentials suitable for untrusted arbitrary agent programs.

## Evidence and failure rules

The normalizer preserves the validated PR base ref and merge commit SHA. A report is verified only when both sources are healthy and observed within 20 minutes, the PR is merged to `scentai-mvp`, PR head matches its expected head, its merge commit matches the expected merge SHA, and the exact registered CI run succeeded on that same SHA. The CI normalizer independently requires the integration branch and `.github/workflows/ci.yml`.

Every completed audit stores a bounded report and SHA-256 hash in the service-only evidence table. Failed/stale/conflicting verification releases the lease and blocks the task with the exact reason. Reports explicitly deny inferred approvals and deployment verification. No token, workflow log, source HTML or chat history enters the packet. Existing acceptance receipt projection includes the fifth exact key, `jarvis.ci_pr_verifier.acceptance`.

The 20-minute bound is an evidence policy for a known final CI/PR pair, not an extension of purchase freshness or a change to its 72-hour gate. Registration of future exact targets is still required from the trusted post-merge flow; this handler does not discover or authorize arbitrary PRs.

## Sequential optimization candidates

Scores are ordinal 1–5, ordered by impact × frequency × manual effort × safety × verifiability. Scores are engineering prioritization, not measured production telemetry.

| Candidate | I | F | M | S | V | Score | Disposition |
|---|---:|---:|---:|---:|---:|---:|---|
| Purchase pre-expiry verification | 5 | 5 | 4 | 4 | 5 | 2000 | Implemented and live certified first |
| Exact CI/PR correlation | 4 | 5 | 4 | 5 | 5 | 2000 | This sequential handler |
| Exact post-merge deployment verification | 5 | 4 | 4 | 4 | 5 | 1600 | Next priority; autonomous Render credential missing |
| Additional merchant parser coverage | 4 | 4 | 4 | 3 | 4 | 768 | Merchant-specific identity/price/stock contracts required |
| Dependency/state freshness and receipt checks | 3 | 4 | 3 | 5 | 4 | 720 | Existing state auditor, dependency events and receipt projector cover core work |
| Known external response reconciliation | 3 | 3 | 4 | 3 | 4 | 432 | Gmail credential/OAuth owner provisioning blocks activation |

`OPTIMIZATION_CANDIDATE`: exact post-merge deployment verification. Problem: green CI and a merged PR do not prove the service serves that commit. Cause: Render autonomous observer lacks a durable credential. Automation: correlate the exact expected merge SHA with a fresh `live` deployment for the one allowed service, then existing smoke evidence. Benefit: remove manual deployment/SHA checks and chat dependence. Risk: broad Render account tokens; use the documented fixed-GET broker or a dedicated automation identity. Priority: next after this handler's live acceptance.

`OPTIMIZATION_CANDIDATE`: wider merchant pre-expiry coverage. Problem: other merchant offers still require manual verification. Cause: the exact parser contract intentionally covers only the certified Perfumetrader offer. Automation: one merchant-specific deterministic parser and unchanged-business-field policy at a time. Benefit: prevent further expired eligible-offer evidence. Risk: ambiguous product identity, shipping or price semantics. Priority: after exact source contracts can be established; never infer coverage from the 1 Million acceptance.
