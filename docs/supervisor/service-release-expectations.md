# Service release expectations

The production branch, API and storefront have separate release scopes. A SQL
migration or documentation commit does not itself require either Render service
to deploy. Conversely, a deliberately retained API release does not establish
that newer API code is already running or equivalent to that release.

`read_dufynd_render_release_expectations_v1()` provides one classification used
by both `read_dufynd_technical_work_blockers_v1()` and
`audit_dufynd_integrity_v1()`. A SHA difference is compared with an explicitly
approved service release, rather than treating monorepo HEAD as every service's
deployment target. Actual provider snapshots and their timestamps are unchanged.

## Private approval contract

The existing private masterstatus table stores one document at
`ops.render_release_expectations_v1`. The migration creates no approval, observer
or task. The authorized release operator writes the first document only after
the final production HEAD and the actual approved service releases are known.
The table remains protected by its existing RLS and postgres/service_role grants.

The version-1 envelope accepts exactly these fields:

| Field | Required meaning |
| --- | --- |
| `version` | JSON number `1`. |
| `repository` | `tncommerce/commerce-agents`. |
| `branch` | `scentai-mvp`. |
| `repository_head_sha` | Full lowercase 40-character SHA, equal to the current fresh GitHub branch observation. |
| `approval_status` | `approved`, under an actual existing release authorization. |
| `approved_at` | Finite ISO timestamp with explicit timezone, not in the future. |
| `valid_until` | Optional finite ISO timestamp with explicit timezone. Omit when absent; JSON null is invalid. If present, it must be after approval and still in the future. |
| `services` | Exactly one entry for each fixed service below. |

The row's `last_verified_at` must be finite, nonfuture and at least `approved_at`.
The contract has no artificial periodic approval requirement: it binds exactly
one repository HEAD. A changed or unverified HEAD invalidates that binding; an
explicit `valid_until` also limits it. Unknown fields or partial, duplicated,
mistyped, swapped or expired bindings produce an unknown diagnosis.

Every service entry accepts exactly the following string fields:

| Field | API | Storefront |
| --- | --- | --- |
| `component` | `api` | `storefront` |
| `service_id` | `srv-dakpfrnf3r2c73dr3f20` | `srv-dakpiajl550s73cp4lvg` |
| `scope` | `api_runtime` | `storefront_static` |
| `expected_deployment_sha` | Full explicitly approved deployment SHA. | Full explicitly approved deployment SHA. |
| `decision` | `hold_existing_release` or `deploy_approved_release`. | Same two explicit choices. |
| `evidence_ref` | Nonblank bounded reference to the actual release decision/evidence, at most 500 characters. | Same requirement. |
| `rationale` | Nonblank explanation of that service's release scope, at most 1,000 characters. | Same requirement. |

At the start of this change, the approved intended hold is API
`7f63836c1e1f837e1dc72e3ab0e12090a97d8112` and storefront
`063f4f2ca0a6403137c6f5e94a71f0ec593e6a98`. The newer Commerce API changes are
deliberately not deployed. Those SHA values are context for the operator's
decision, not seeds or permanent exceptions in the function. The final binding
must name the actual post-merge HEAD and its release evidence.

## Intent and provider evidence are separate

The helper always reports both fixed services, even if one has no observer.
Additional enabled Render services are reported separately with unknown release
expectations; they cannot borrow either fixed service's approval.

For each service, `intent_match` compares an identity-valid observed SHA with the
approved deployment SHA. `observation_verified` additionally requires a unique,
enabled, healthy and fresh Render observer, matching observer/source/snapshot
service IDs, a `live` deployment state and a valid nonempty `dep-…` deployment
ID. The existing freshness bound remains `greatest(600, interval_seconds * 3)`;
missing, future or nonfinite success timestamps cannot pass.

`comparison_status=aligned` requires both an approved HEAD-bound intent and
verified current provider evidence. A stale matching snapshot can have
`intent_match=true` while `observation_verified=false`; its comparison remains
unknown. A fresh wrong deployment is a mismatch. The report never asserts code
equivalence between different revisions.

The recorded runtime currently has an API observer with stale evidence and no
storefront observer. Registering an intent therefore cannot make this runtime
healthy. Storefront coverage remains explicitly missing until a real approved
observation path exists; this migration does not fabricate one.

Private provider freshness, blocked Gmail configuration, full broker capture
acceptance bound to the actual executed source revision, and public API health
remain independent checks. Existing ready/active tasks and genuine owner gates
retain precedence in the planner.

## Independent public storefront availability

The technical reader also includes `read_dufynd_public_storefront_health_v1()`
under `public_storefront_health`. An enabled monitor with a pending, stale,
unhealthy or unavailable receipt adds the corresponding
`public_storefront_health_pending`, `public_storefront_health_stale`,
`public_storefront_unhealthy` or `public_storefront_health_unavailable` issue.
The existing free planner and integrity audit consume those current issues;
they do not create synthetic work or relabel an empty queue as starvation.
A deliberately disabled monitor is visible as disabled, without a false outage.
The planner retains its existing API-first diagnostic priority, then selects
`diagnose_public_storefront_health` for a current storefront problem before the
private-observer fallback. Existing runnable work and owner gates still win.

API availability and storefront availability remain independent of each other
and of private provider evidence. A valid public HTML response proves only the
bounded homepage availability contract. It cannot establish a Render deployment
revision, final redirect origin, private broker acceptance, a functioning buying
journey or a business action. `private_technical_work_remaining` continues to
reflect only the independent private checks. A stopped poller cannot preserve
public health beyond the reader's actual receipt expiry.

`tests/test_dufynd_public_health_integration_postgres.py` installs the actual
storefront reader together with the existing release classifier, free planner
and integrity audit. Its local fixture supplies non-secret receipt metadata;
it performs no HTTP requests. The separate storefront transport suite exercises
receipt cardinality, HTML validation, backoff and the existing scheduled hook.

## Explained monitoring work and starvation

The audit previously labelled an empty queue as planner starvation even when the
planner had already diagnosed real technical work. A diagnosis now explains that
empty queue only when its masterstatus timestamp is finite, nonfuture and within
600 seconds, its state is `technical_remediation_required`, and both its stored
technical flag and the independently reread current technical flag are strictly
boolean true. The normal planner runs every two minutes; the 600-second bound
uses the existing minimum evidence window without changing any schedule.

`technical_diagnosis_current` records this distinction. It does not mark the
system healthy: the audit also retains the actual current technical issue codes
and detail object, deduplicated with its existing findings. Partial or wrong-SHA
broker captures and public-health errors remain degraded. Missing, stale,
malformed or now-resolved diagnoses cannot hide genuinely unplanned work, and
`ready_work_not_claimed` remains independently active.

## Verification and release boundary

`tests/test_dufynd_service_release_expectations_postgres.py` executes the helper,
real technical reader, exhaustion reader, free planner and integrity audit in
disposable PostgreSQL. It reuses the existing planner fixture, does not call any
provider, and rolls back observation, contract, task and function changes.

Coverage includes explicit service holds, unknown approval despite coincidental
SHA equality, fresh mismatches, exact source identity, nested JSON types, malformed
and timezone-invalid dates, duplicate/partial/swapped scopes, missing and extra
services, unhealthy/stale/non-live observations, independent operational gaps,
explained versus genuine starvation, existing-work precedence, ACL preservation
and migration idempotency. The existing PostgreSQL CI job includes the new file;
no job, runner, cron or deployment is added.

Local PostgreSQL 17.11 verification on 2026-10-29 passed all 113 initial cases.
One additional cross-test then passed independently, bringing verified coverage
to 114 cases without rerunning those 113. It installs the actual release audit,
credential-health function and paused Gmail reconciliation/wrapper in one
transaction: real technical issues remain degraded, `planner_starved=false`,
revoked Gmail still requires reauthorization, and the existing explicit pause
keeps `owner_action_required=false`. Observations, credentials, tasks and the
pause policy remain unchanged by that complete call chain.

Three
selected tests against the unchanged production functions failed at the intended
semantic assertions: an approved service hold was misclassified as degraded,
coincidental HEAD equality passed without release intent, and a current explained
technical diagnosis was labelled planner starvation. Ruff lint/format and patch
whitespace checks passed. These local results do not replace the existing
mandatory pull-request checks.

The migration preserves the old readers' ACLs, volatility and security mode. The
new helper is stable and security-invoker, executable only by postgres and
service_role. It issues no network request and performs no data write. Rollback
would restore the prior conservative but overly broad SHA comparison and
starvation classification; provider evidence must not be rewritten to make a
rollback appear healthy.
