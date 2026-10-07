# Observer reliability

Purchase freshness is an event-driven dependency. The two-minute supervisor wake
checks the registered target even when no verification is due. Its observer
snapshot records `purchase_target_scheduler`, the original merchant verification
date and the actual due date. A successful scheduler check is **monitored**, not
a new merchant read. Missing or disabled targets fail closed. Existing due-event
deduplication and verification evidence remain authoritative.

The dashboard distinguishes initializing, initializing_stuck, healthy, monitored,
stale, blocked_configuration and failed. An initialization becomes stuck only
after its retry deadline has been overdue for at least three intervals (minimum
six minutes). A retry deadline never implies a successful observation.

Gmail refresh stays inside the private broker. The GitHub Actions change bridge
dispatches the existing fixed `scentai-mvp` workflow after observer code changes;
the push job has no OIDC permission. Broker trust remains limited to the existing
dispatch/schedule contract. Provider credentials never enter Actions or tasks.
This bridge is not a recurring scheduler replacement. GitHub scheduled execution
can be delayed; old captures must remain stale/blocked until a new accepted read.
Token expiry alone does not prove an owner reauthorization is required. A private
refresh result such as invalid_grant or revoked credentials does.

## 2026-10-07 live recovery evidence

Direct Gmail access remained healthy while the private observer projection showed
the three bounded Gmail thread observers as `blocked_configuration /
credential_expired`. The underlying broker credential still retained refresh
metadata; no evidence of `invalid_grant`, revocation, account mismatch or scope
mismatch was observed.

The accepted private observer workflow most recently completed successfully on
`scentai-mvp` as run `37624824247`. Because the default-branch cron is not
meeting the intended cadence reliably on the public fork, a normal
`scentai-mvp` push is also an intentional bounded recovery trigger: it dispatches
the existing OIDC-constrained read path, which performs credential refresh inside
the private broker before any Gmail metadata read. This preserves the existing
secret boundary and introduces no provider spend.

A successful push-triggered refresh proves the broker and refresh token are still
usable; it does **not** by itself prove that recurring default-branch scheduling
is reliable. Scheduler reliability remains a separate gate and must only be
marked healthy after fresh automatic schedule evidence is observed.

Validation: Python projection/credential/workflow regressions, PostgreSQL tests
of future retry dates and unchanged merchant verification truth, and the existing
full private read → durable capture → ack → activation workflow after merge.
