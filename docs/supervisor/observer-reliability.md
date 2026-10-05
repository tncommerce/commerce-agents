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

Validation: Python projection/credential/workflow regressions, PostgreSQL tests
of future retry dates and unchanged merchant verification truth, and the existing
full private read → durable capture → ack → activation workflow after merge.
