# Separate API and Storefront deployment observations

## Scope and rollout state

The existing `render` workflow mode continues to use the API-only v1 broker and
capture contract. This extension adds an explicitly selected
`render_services_v2` mode. Committing or merging its source does not deploy the
broker, enable its new scope, register an observer or change a schedule.

The two permitted services are fixed in code and SQL:

| Component | Render service |
| --- | --- |
| API | `srv-dakpfrnf3r2c73dr3f20` |
| Storefront | `srv-dakpiajl550s73cp4lvg` |

No task, URL parameter or workflow input can select another service, a Render
mutation, settings, environment variables, logs or a Gmail operation. The
existing provider secret stays in the owner's broker. GitHub Actions retains
its existing short-lived workload identity; it receives no deployment identity
or provider key.

## Why the v1 credential stays unchanged

V1 describes one API-only resource and one provider-level health timestamp.
Reusing that timestamp for two services could make an unobserved Storefront
appear fresh. Widening its existing resource metadata would also break existing
health and acceptance consumers.

V2 therefore has a separate explicit permission scope, `render_services_v2`.
It uses the existing Render credential as a common capture and health-projection
kill-switch while leaving that credential's v1 metadata intact. SQL revocation
does not remove the broker's mounted provider key or disable an already enabled
read-only probe; the runtime gate is a separate control. The new private
SQL scope grants are separately disabled by default and writable only by the
database owner. The service-role capture can read grants, not enable them.

The broker separately requires
`BROKER_RENDER_SERVICES_V2=api-storefront-v2`. An absent or empty value leaves
the new paths disabled. Any other nonempty value fails configuration validation.
An image update alone cannot opt into the wider read scope.

## Per-service response and strict artifact

The authenticated fixed path is
`/v2/render/services/{fixed_service_id}/deployments`.
Each successful response has exactly these keys:

```json
{
  "version": 2,
  "scope_id": "render_services_v2",
  "service_id": "srv-dakpiajl550s73cp4lvg",
  "observed_at": "2026-10-29T10:00:00+00:00",
  "deployments": [
    {
      "deployment_id": "dep-example",
      "service_id": "srv-dakpiajl550s73cp4lvg",
      "commit_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "status": "live",
      "timestamps": {
        "createdAt": "2026-10-29T09:00:00Z",
        "updatedAt": "2026-10-29T09:01:00Z",
        "startedAt": null,
        "finishedAt": "2026-10-29T09:01:00Z"
      }
    }
  ]
}
```

The example is illustrative, not production evidence. `observed_at` is generated
only after that service's upstream GET and filtered response validation complete.
V2 does not read or update Gmail, the broker vault or the v1 global health record.
Responses have bounded bodies, one to twenty unique deployments and exact
service bindings. Redirects, duplicate JSON keys, non-finite JSON numbers and
malformed timestamps are rejected. The broker filters extra upstream provider
fields; the resulting envelope and artifact reject unexpected fields.

`broker-render-services-v2.json` contains `_meta`, `version`, `services` and
`failures`. Its successful and failed service keys must form an exact disjoint
partition of the two fixed services. Failure values are bounded reason codes,
never raw response bodies or exception text. The full artifact is validated
before any database capture. Its provenance binds the existing immutable
repository and owner IDs, trusted workflow/ref, source SHA, run ID and attempt.

## Partial failure, retries and revocation

Each service uses the RPC
`capture_dufynd_render_service_read_v2(p_source,p_observation)` and an independent
durable receipt and watermark. Both services may be captured in one run and
attempt. An identical retry can return its existing receipt but cannot refresh
the observation, capture or health time. Conflicting replays, superseded
attempts/runs and stale or future observations fail closed.

A failed peer does not discard a valid independent observation. Read and capture
commands still return a failing exit status when complete requested coverage
was not achieved. No receipt claims business success, complete private-provider
acceptance, Gmail capture, acknowledgement or activation.

The private scope must remain enabled, have an explicitly recorded verified
runtime image and have an enabled matching observer. The common Render
credential must remain permitted. Revoking scope or the credential must not
leave a v2-marked snapshot reported as healthy. Re-enabling a scope alone does
not supply a new observation. The normal observer poller retains responsibility
for freshness and degraded-state reconciliation; no extra cron is introduced.

## Staged activation in the existing owner environment

1. Verify the exact combined source tree through the normal protected PR checks.
   The browser QA for unchanged Storefront source need not be rerun.
2. Inspect the existing live schema and apply the reviewed additive migration
   only with its preconditions satisfied. Both new service grants remain off;
   the migration does not register or enable a Storefront observer.
3. Establish the actual existing owner-controlled broker target and deployment
   channel, not a template project name. Verify existing available capacity under
   the standing zero-additional-cost constraint. Do not create resources or
   change billing to make this procedure work.
4. Deploy the exact approved image to the verified existing broker using the
   guarded owner helper. Keep v2 off initially and verify that the existing v1
   path still works. The helper changes only the image; it does not set the v2
   environment variable or change IAM, secrets, scaling or traffic policy.
5. Through the same authenticated owner channel, explicitly enable the broker's
   non-secret v2 scope. Verify its actual ready revision, image digest and traffic
   after that configuration revision as well. Do not grant GitHub or Jarvis GCP
   deployment rights.
6. Set the existing repository's separate
   `DUFYND_PRIVATE_RENDER_SERVICES_V2_ENABLED` flag only after the runtime is
   verified. Select workflow mode `render_services_v2` with `capture_v2=false`
   for a bounded read-only probe. The existing broker-enabled flag is also
   required. Inspect both real envelopes and their exact run/attempt artifact.
7. Record the verified runtime proof and explicitly enable the intended SQL
   service grants and matching observer registrations through the existing
   owner/database channel. Do not manufacture a success timestamp or overwrite
   the legacy API credential's resource list.
8. Select the same explicit mode with `capture_v2=true`. Verify each durable
   receipt, service SHA/status, original observed time and the subsequent normal
   health cycle. An attempt with a failed peer remains partial.
9. After real v2 capture and the normal health cycle are verified, verify the
   gated dispatch source on both `main` and `scentai-mvp`. Only then enable
   `DUFYND_PRIVATE_RENDER_SERVICES_V2_AUTO_ENABLED=1` for the existing automatic
   triggers. Leave this separate flag absent or off during runtime/read-only
   acceptance. A source merge does not enable it.

If the existing project, authentication, API access or cost headroom cannot be
verified, preserve the disabled state and record the concrete capability gap.
A permission failure is not evidence that a replacement project is needed.

## Automatic dispatch gate

The two existing dispatchers on `main` (reader and watchdog) and the existing
`scentai-mvp` push fallback send exactly one dispatch to the trusted observer
workflow. They select `mode=render_services_v2` with `capture_v2=true` only when
all three repository variables are exactly `1`:

- `DUFYND_PRIVATE_BROKER_ENABLED`
- `DUFYND_PRIVATE_RENDER_SERVICES_V2_ENABLED`
- `DUFYND_PRIVATE_RENDER_SERVICES_V2_AUTO_ENABLED`

Otherwise an executing dispatcher explicitly selects `mode=render` and
`capture_v2=false`. Inputless manual dispatches retain the `render` default.
The new AUTO flag separates automatic capture from the preceding manual probes;
it does not replace runtime, SQL grant or per-service observer verification.
No flag is written by the workflow. Transport failures remain failed steps,
without a second dispatch or an automatic retry. Gmail recovery remains paused.

The trigger schedules, permissions and concurrency are unchanged. Source and
offline transport tests prove routing, not timely GitHub schedule delivery or a
successful downstream observation. Continue checking the original observation
and durable capture times; do not widen freshness thresholds to hide late runs.

## Safe rollback

Disable `DUFYND_PRIVATE_RENDER_SERVICES_V2_AUTO_ENABLED` first to stop automatic
v2 selection. Disable the explicit v2 SQL service grants and stop selecting v2
in manual dispatches.
Preserve their receipts for audit; a rollback must not erase the evidence or
invent fresh v1 observations. Disable the broker's v2 gate through the verified
owner channel when required. The unchanged v1 API workflow remains available.
Do not automatically redeploy, delete the private tables or reset credentials.
The guarded [operational rollback](../../release/dufynd-render-services-v2-20261029/rollback.sql)
requires every SQL scope disabled and the marked observers already reconciled.
It verifies the exact poller body before removing its v2 reconciliation call and
revokes service-role execution of the v2 capture RPC. Scope proofs, receipts,
events and the original v1 path are retained.

## Verification boundaries

Local tests use fake upstream providers and isolated PostgreSQL. They cover the
HTTP/runtime gates, per-service time and filtering, bounded parsing, strict
artifact/receipt validation, partial failures, scope privileges, concurrent
capture/revocation, idempotence and the ordinary health cycle. They cannot prove
that the owner runtime has been deployed, that a new private Storefront capture
exists, that GitHub schedules meet a reliable cadence or that extra paid capacity
is available. Record those separately from CI success.
