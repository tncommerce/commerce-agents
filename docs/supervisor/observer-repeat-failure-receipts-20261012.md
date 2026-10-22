# Observer repeat-read failure receipts — development only

The read harness already refused changed Gmail pending-observation redelivery and stopped on revoked credentials. However, only initial read failures wrote `broker-failure.json`. A failure during one of the three redelivery checks therefore left no sanitized receipt for the existing durable failure-ingestion job. The importer also rejected repeat-stage identifiers. This is a diagnostic gap, not evidence that the live revoked credential can recover without the owner.

The same bounded failure writer now handles initial and repeat read stages. Import validation shares the fixed stage allowlist and accepts `pending_redelivery_mismatch`. Unknown response-body diagnostics are still reduced to HTTP status. OIDC and provenance errors remain outside provider receipt ingestion. No retry, cursor acknowledgment, partial observation capture, credential change, new endpoint, scope expansion, workflow change or database migration was introduced. The existing Gmail reconciliation uses `stage LIKE gmail_%` and thus already recognizes the bounded repeat stages.

Validation: 10 regressions failed on the released implementation. The corrected narrow read/ack/credential/workflow suite passes 58 tests; Ruff lint and format pass. All calls use FakeClient or httpx.MockTransport; no Gmail, OAuth or broker access occurred. Every repeat position and revoked, rate-limited, unknown-sensitive reason is covered, with strict call counts, no partial success artifact and successful failure-import validation. Invalid fourth Gmail repeat stages remain rejected.

Deployment remains HOLD: this is a reliability improvement, not an emergency production fix. The actual `gmail_1:revoked` incident still requires the existing owner broker flow `/owner/oauth/gmail/start`, followed by three fresh accepted metadata reads through the authorized workflow. No blocked authentication was retried.

## Transport-stage follow-up — 2026-10-13

A separate reproduced gap remained after the HTTP/repeat fix: `httpx.ReadTimeout`
and `httpx.ConnectError` escaped to the generic internal-error handler, so no
bounded stage receipt survived. Sixteen new cases failed on04cdcf4f (both errors
at render, health, all three initial Gmail reads and all three repeat reads).

The fixed broker-read helper now maps only `httpx.TransportError` to the literal
`transport_error` at that exact stage, feeding the existing receipt path and
shared importer allowlist. Provider exception strings, URLs and tokens never
enter the receipt. No retry, login, cursor acknowledgment, partial-observation
publication, health recovery claim or credential change is added. A transport
failure is not labelled revoked. OIDC failures remain outside broker receipts;
unexpected programming errors retain their existing generic failure handling.

49 read/ack/workflow regression tests pass, including16 reproduced failures and
2 scope-isolation cases. Ruff lint/format and diff checks pass. All requests in
these tests are fake clients; the real `gmail_1:revoked` OWNER_HOLD remains.
Exact-head new-code CI is recorded in PR778. This diagnostic improvement remains
development-only and is not a production emergency release.
