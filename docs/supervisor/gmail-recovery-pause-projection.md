# Respect the existing Gmail recovery pause in recurring status

## Observed inconsistency

On 2026-10-29 at 10:00 UTC, the recurring integrity status still reported
`owner_action_required=true` and the Gmail alert asked for another OAuth start.
The existing privileged scheduler status had already recorded
`gmail_recovery_paused=true` and `owner_action_required=false` at 06:58 UTC.
The current user instruction also keeps Google/Gmail recovery paused.

The cause was `reconcile_dufynd_gmail_health_v1()`: its persisted owner gate
correctly retained a revoked-grant incident, but did not distinguish that incident
from a request for the owner to act now. `audit_dufynd_integrity_with_gmail_v1()`
then projected that request into every regular integrity report.

## Contract

The forward migration reads the existing private masterstatus key
`jarvis.private_observer_scheduler_v1`. A pause is recognized only when its value
is an object, `gmail_recovery_paused` is the JSON boolean `true`,
`owner_action_required` is the JSON boolean `false`, and `last_verified_at` is
finite and not in the future. Missing, conflicting or wrongly typed directives
preserve the existing alert behavior. An explicit pause has no artificial expiry;
its removal must be a deliberate change to that existing directive.

For a recognized pause, the current Gmail action says that recovery is paused.
The report separately preserves:

- the actual credential or observation problem in `state`;
- `reauthorization_required`, when the underlying incident requires it;
- `recovery_paused` and the exact `pause_policy_source`;
- the original incident deduplication key and first observation time;
- the requirement for healthy credentials and three fresh broker reads before
  `recovered` may be returned.

The integrity wrapper combines the Gmail action with any independent base-audit
owner gate using logical OR. Pausing Gmail cannot hide a different owner decision.
Existing degraded issues remain present.

This changes the recurring SQL alert and integrity projection. It does not
complete Gmail recovery, activate credentials, request a login, initiate a refresh,
send a message, dispatch a workflow, or change a schedule. Existing expiry
classification continues unchanged. It does not rewrite historical reports or
claim that an unchanged API deployment has acquired new behavior.

## Validation and release

The native PostgreSQL tests reproduce the ignored pause with the exact previous
function, then verify strict policy parsing, missing/conflicting directives,
future/nonfinite metadata, deliberate resume, persistent pauses, unchanged
credential and observer evidence, real recovery gates, unrelated owner gates,
recurring report persistence, restricted EXECUTE privileges and migration reapply.
Provider requests are unnecessary for this verification.

Before applying, compare the existing function source hashes with the reviewed
baseline:

```text
reconcile_dufynd_gmail_health_v1: 496314500fa526664fda348727121fd6
audit_dufynd_integrity_with_gmail_v1: f087b18cea3a7cd62b5be3c7ad343208
```

After the protected code merge and tested migration, inspect the next regular
integrity report. A revoked Gmail grant must remain visible while the current
Gmail owner request becomes false. The scheduler pause document itself is not
modified by this migration. No new production request is needed for acceptance.
