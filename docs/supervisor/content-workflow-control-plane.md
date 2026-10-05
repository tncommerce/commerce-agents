# Autonomous content QA control plane

`dufynd_content_workflows` is opt-in state for future candidates. There is no
backfill or mutation of existing assets/schedules. Jarvis uses
`advance_content_workflow` on its existing bridge. Compare-and-set transitions
reject stale workers. The state row is separate from asset metadata so recording
progress cannot accidentally change the owner-review revision fingerprint.

Brief → product truth → rights → creative request/receipt → internal review →
quality → mobile preview → click path → final owner review → owner approval →
schedule observation → publication observation/verification → measurement →
learning. The last stages record verified observations only; no generator,
scheduler, publisher or approval resolver is called by the transition RPC.

Every proof supplies PASS, an evidence reference, an observation timestamp and
the exact current revision fingerprint. Missing, future-dated, failed or outdated
proofs are rejected. Final QA requires product truth, rights, exact fidelity,
dimensions/platform format, mobile preview, factual copy, click path and visual
quality at 9.5–10. Collect the complete self-review packet before quality_pass;
the subsequent mobile/click stages record their specific successful checkpoints.
The existing V2 upload/native-preview/platform-CTA gate still applies before a
pending owner decision can be created. Owner approval must already exist for the
same candidate fingerprint. This module never writes an approved decision.

Service-role evidence producers must reference actual stored reviews or provider
observations. An evidence reference is not proof of a sale. Publication,
measurement, network transactions and commission remain separate facts.
External-stage records do not authorize any external action. Publishing remains
in the separately owner-authorized content workflow.

A changed asset version/URI/metadata resets QA to brief_ready with a visible
revision blocker. Internal review failures route to at most three revision
requests. A new revision requires a complete new review packet. The generator
adapter currently dispatches nothing and returns
approved_free_generator_unavailable. No paid fallback exists. Integration with a
future approved generator requires a separate reviewed adapter implementation.

CI uses a disposable Postgres database to test CAS, revision invalidation, all
individual QA failures, the score floor, real-owner-decision checks and the
private RPC privilege boundary. No production fixture assets or approvals are
created.
