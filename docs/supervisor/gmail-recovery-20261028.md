# Gmail recovery: one owner renewal, then a new complete observer run

Evidence date: 28 October 2026. This change is prepared locally on production
commit `89aae8925e606caa33f8f7dafa3edbeafab32c3c`. It does not perform OAuth,
read a credential, modify activation, deploy a broker, or create a scheduler.

## Live delta and the scope of PR #802

- [PR #802](https://github.com/tncommerce/commerce-agents/pull/802) is still draft
  at `39978a57820e7dbd68d22b803c748fe46a556554`, with five changed files. Its
  existing [CI 39070073648](https://github.com/tncommerce/commerce-agents/actions/runs/39070073648)
  succeeded. Those results were reused, not rerun.
- A local merge calculation against exact production `89aae892…` is conflict-free:
  combined tree `36d5f2a45eee75dc8cbfcaff76582ef21faafebc`. This is mechanical
  compatibility evidence, not a new runtime or deployment acceptance.
- #802 adds an independent, disabled-by-default Google OIDC refresh trigger.
  It does not repair a revoked grant, perform ingestion, ACK a Gmail cursor, or
  finalize an acceptance session. It is not a prerequisite for the immediate
  credential recovery. Its separate Cloud Scheduler/IAM/cost gates remain intact.
- The latest production observer run returned by the GitHub API during this
  review was [40662804800](https://github.com/tncommerce/commerce-agents/actions/runs/40662804800),
  attempt 1, created at 09:15:18 UTC on `89aae892…`.
  [Read job 122729756385](https://github.com/tncommerce/commerce-agents/actions/runs/40662804800/job/122729756385)
  reported `gmail_1:revoked` at 09:15:43 UTC. The failure-receipt job succeeded;
  ingest, ACK, and finalize were skipped. No Gmail recovery is established.
- A configured five-minute dispatcher interval does not prove five-minute
  executions. Recovery must cite a new actual workflow run, not infer one from
  cron configuration or reuse the old failed run's receipt.

## Confirmed new handoff defect and bounded fix

The failure path already checked `run_attempt`. The successful path checked only
`run_id` and SHA, while its filtered-read, ACK-plan and ACK-receipt artifact names
also omitted the attempt. A later attempt could select earlier-attempt evidence.
Re-uploading the same name is also incompatible with immutable Actions artifacts;
see the official [artifact migration guidance](https://github.com/actions/upload-artifact/blob/main/docs/MIGRATION.md).

An offline reproduction against unchanged `89aae892…` set the running attempt to
2 while supplying source-attempt-1 evidence. The fake control plane accepted one
health projection, four captures, six ACK requests and one finalize call. These
were local fakes with zero network requests, not production writes.

The patch now:

1. Binds every successful handoff to the expected `run_id`, SHA **and attempt**,
   before health projection, capture, OIDC retrieval, ACK or finalization.
2. Includes `github.run_attempt` in all three success-artifact names and their
   exact downloads, matching the already protected failure-artifact path.
3. Requires `GITHUB_RUN_ATTEMPT` or the corresponding explicit CLI argument at
   operational entry points. Missing provenance fails before bridge creation or
   network access.

No credential, OAuth scope, broker endpoint, provider identity, activation gate,
database function or scheduled job changes. ACK remains contingent on all four
durable captures; three idempotent ACK rechecks remain required before finalize.

## Exactly what the owner must do

The private broker reports a terminal revoked state. Its refresh implementation
intentionally refuses that state; repeating refresh jobs cannot restore it.

The required intervention is **one fresh authorization of the existing private
broker using the mailbox already configured for it**:

1. The owner or existing authorized private-project operator uses the existing
   owner-only `POST /owner/oauth/gmail/start` from their secure local client. The
   owner key stays in that private environment. It is not copied into ChatGPT,
   GitHub Actions, Supabase, this repository or a task packet.
2. The owner opens the newly returned Google authorization URL, selects the
   configured mailbox and consents once to the existing exact
   `https://www.googleapis.com/auth/gmail.metadata` scope. No broader mail scope,
   new client or new service account is needed for this recovery.
3. The existing callback consumes the short-lived PKCE/state session once,
   verifies the mailbox and scope, and stores the new credential atomically in
   the private encrypted vault. Codes, callback queries, tokens and private keys
   must not be pasted into a handoff. Existing callback-log protections remain
   mandatory. Use a fresh authorization URL if that single session has expired;
   do not replay a callback or start recurring login attempts.

The observed reason does not establish why Google invalidated the grant.
Google documents revocation, Gmail-scope password changes and other causes.
For an external OAuth app still in **Testing**, non-basic scopes can result in
a seven-day refresh-token lifetime. The private-project operator should check
that existing app's publishing/policy metadata once before treating consent as
a durable repair. The app's actual status was not read in this review; no
publishing or policy setting was changed. See [Google's refresh-token guidance](https://developers.google.com/identity/protocols/oauth2#expiration).

## Full-chain acceptance after that intervention

Use a **new workflow run ID** from the existing trusted production observer
workflow. The existing dispatcher may supply it; if delayed, the existing
owner-authorized manual workflow is the bounded fallback. No new automation or
credential-sharing capability is required.

- Read: current production SHA; fixed Render service plus all three allowlisted
  Gmail threads; healthy/expiring metadata captured after those reads.
- Ingest: the current run/attempt artifact only; fresh bounded health projection;
  an acceptance session in `recurring_read` mode when both existing activations
  remain enabled; four accepted durable captures.
- ACK: the three exact accepted digests; first-pass acknowledged plus duplicate
  counts total three; all three second-pass replies are duplicate.
- Finalize: the same run/SHA/attempt; matching ACK receipt; session reaches
  `activated` with a real `finalized_at`, all expected captured observers and
  `activation_changed:false` for recurring recovery.
- Observation: all three Gmail `last_success_at` timestamps actually advance.
  Only then report the full observer chain recovered. This still does not prove
  a new merchant reply, a task completion, a clickout, a sale or a commission.

The database keeps one acceptance identity per `run_id` and rejects a different
attempt after a session has begun. This guard is deliberately unchanged. After
partial ingestion/ACK, use a new complete run ID; do not reuse an old acceptance
or re-run only later jobs with prior-attempt artifacts. A second attempt before
any acceptance began can use its own newly produced evidence. Neither case
requires repeated owner consent once the credential is healthy.

## Verification and remaining release gate

- 72 focused Python cases passed, including 13 new attempt-boundary cases:
  old/future attempt rejection before side effects, successful current-attempt
  complete handoff with fake OIDC/ACK/control plane, missing-attempt rejection,
  and matching unique producer/consumer artifact names across attempts.
- Existing affected read, independent Render recovery, ingest, ACK, finalize
  and workflow tests were included. Ruff, formatting and `git diff --check` passed.
- The unchanged database acceptance contract already passed in production
  release CI [40661816326](https://github.com/tncommerce/commerce-agents/actions/runs/40661816326)
  (262 PostgreSQL tests). No database migration is included in this patch.
- No remote CI, PR publication, merge, workflow dispatch, credential read,
  consent, activation or deployment was performed by this review.
- Before releasing this patch to production, bind normal required CI to its
  final integrated head and coordinate the workflow change with the active release.
  Local fake success is not an actual Gmail recovery receipt.

Focused local command (existing isolated Python environment; no package install):

```sh
PYTHONPATH=commerce-common:merchant-agent/core:shopping-agent/core \
  /tmp/dufynd-venv/bin/pytest -q \
  tests/test_dufynd_private_observer_attempt_boundary.py \
  tests/test_dufynd_private_observer_ingest.py \
  tests/test_private_broker_observer_ack.py \
  tests/test_dufynd_private_observer_finalize.py \
  tests/test_dufynd_private_observer_workflow.py \
  tests/test_dufynd_render_observer_recovery.py \
  tests/test_private_broker_observer_read.py
```
