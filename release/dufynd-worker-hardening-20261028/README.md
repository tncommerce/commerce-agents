# DUFYND worker and API hardening — 28 October 2026

Base: `89aae8925e606caa33f8f7dafa3edbeafab32c3c`, released through #842.
The six required integration checks for that base passed in run `40661816326`.
This follow-up contains two newly reproduced defects and their bounded fixes.

## API event-loop isolation

Synchronous merchant-evidence reads occurred inside asynchronous catalog handlers
and the merchant-offer scope guard. A slow evidence read could therefore stall an
independent HTTP health request. DUFYND now offloads the complete catalog callback
to the existing Starlette threadpool; scope validation uses only the local catalog
and the unchanged visibility/stock predicates. Other demo hosts keep their current
execution model. The health payload and its liveness meaning are unchanged.

The new real-ASGI regression failed in four cases on the unmodified base. The
corrected focused selection passed 22 cases, including shared-host compatibility.
See [the complete evidence](../../docs/tech/dufynd-catalog-eventloop-20261028.md).

## Observer attempt provenance

Successful read, ACK and receipt artifacts previously bound run ID and commit,
but omitted the workflow attempt. A later attempt could select previous-attempt
evidence. All successful handoffs now bind the expected run ID, SHA and attempt
before capture, identity retrieval, cursor acknowledgement or finalization. The
three artifact producer/consumer pairs use attempt-specific names.

The offline baseline accepted previous-attempt evidence. The corrected focused
suite passed 72 cases, including 13 new attempt-boundary cases. These are local
fakes, not a successful Gmail recovery. Existing database acceptance identities,
activation gates and credential storage are unchanged. After partial acceptance,
recovery requires a new complete workflow run ID.
See [the recovery handoff](../../docs/supervisor/gmail-recovery-20261028.md).

## Release and cost boundary

- No dependency, commerce data, SQL migration, OAuth scope, IAM grant, paid model,
  new scheduler, resource tier, design or billing-setting change.
- Existing CI remains unchanged. The final integrated candidate must pass all six
  normal required checks; the prior large browser QA is reused because this patch
  does not alter storefront code or its dependencies.
- The Render cost gate was checked directly in the authenticated owner dashboard:
  the already purchased Starter block has ample unused minutes, and the existing
  spend limit prevents an additional block purchase. Detailed billing evidence is
  retained in the private Supabase masterstatus, not copied into this public file.
- Use a normal protected merge after successful candidate CI. Suppress automatic
  intermediate Render deployment with `[skip render]`, then deploy the verified
  production commit in a controlled order. No repeated successful CI is needed.
- Gmail remains blocked by the revoked existing grant. PR #802 is an optional,
  default-off scheduler and does not repair that grant. One owner authorization
  and a subsequent real read/ingest/ACK/finalize receipt are still required.

The individual implementation commits were reviewed independently. Their focused
tests are reused; final CI and live deployment receipts belong to the release PR
and existing Supabase masterstatus. This preparation file does not claim a merge,
deployment or Gmail business action has already completed.
