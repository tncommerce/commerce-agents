# Autonomous observer credential boundary

Current implementation: PR #625. See [activation readiness and exact owner steps](observer-activation-readiness.md). The Render/Gmail database poller no longer reads provider tokens or sends direct provider HTTP. The private broker submits only filtered evidence through the service-only ingress. Credential metadata is non-secret; activation is disabled. The refresh/Vault adapter and OAuth callback still require the owner-selected isolated runtime.

The following audit describes the original Phase 2C consumer boundary and is historical where it refers to direct Vault token consumption.

Audit date: 2026-10-02. The connected ChatGPT Render account works for interactive reads; it is not an autonomous worker credential. Vault metadata contains no `dufynd_observer_*` secret. One Render and three known-thread Gmail observers report `blocked_configuration / missing_autonomous_credential`. No secret value was read or exported.

## Minimum access and owner setup

| Service | Minimum operation | One-time owner step | Why needed |
|---|---|---|---|
| Render | GET deployment identity/status for service srv-dakpfrnf3r2c73dr3f20 in TNCommerce; no deploy, restart, settings, logs or secret read | Authorize a dedicated automation identity or a fixed-GET credential broker, then provision its private credential through an owner-controlled secret interface | ChatGPT OAuth cannot be reused by the autonomous PostgreSQL observer |
| Gmail | gmail.metadata, offline OAuth; history IDs and From/Content-Type metadata for the three already registered threads; no body, attachments, search, send or modify | Create/approve a Google OAuth web client, enable Gmail API, approve the redirect URI and grant the selected mailbox gmail.metadata with offline access; store refresh/client secrets in the private broker | The current observer needs renewable access outside a chat; short-lived access tokens alone are insufficient |

Render's official API documentation describes API keys with access to all workspaces of the owning identity. It does not establish a native per-service read-only key scope. Do not label such a key read-only or copy a broad personal key into a task. Prefer a broker that exposes only the exact deployment GET and returns filtered service/SHA/status/time evidence. A broad upstream API key may be considered only inside the separately isolated private broker with an owner-authorized identity; it must never be provisioned directly into Jarvis/Supabase observer state.

The current Gmail transport already uses threads.get with format=metadata and From/Content-Type headers, plus history.list. gmail.metadata is sufficient for these observations; gmail.readonly is unnecessarily broad for this handler. Restrict known-thread IDs in the compiled code in addition to OAuth scope. History events may contain unrelated IDs: discard them before persistence, retaining only known-thread matches. Reply detection never grants rights or sends mail.

## Private secret contract

Historical Phase 2C consumers expected `dufynd_observer_render_read_token` and `dufynd_observer_gmail_read_access_token` in Supabase Vault. Those names are references, not credentials. No placeholder secret should be inserted.

A future private refresh broker owns the Google client secret and refresh token, exchanges only at Google's fixed token endpoint, and atomically updates the access-token Vault entry before expiry. It maintains non-secret metadata: provider, account alias, exact allowed operations/resources/scopes, expires_at, refreshed_at, revoked_at and health reason. Refresh uses a lock and bounded retries; never log response bodies, tokens or Authorization headers. Fail closed on invalid_grant, scope expansion, account mismatch or revocation. Reauthorization is an owner task rather than repeated unattended OAuth attempts.

A Render broker holds the upstream key outside task-accessible storage, allows only GET /v1/services/srv-dakpfrnf3r2c73dr3f20/deploys, filters the response to deployment ID, service ID, SHA, state and timestamps, and refuses redirects, other services, writes and secret endpoints. Its worker token is separately rotatable/revocable. The fixed-read/filtering interface is now implemented; deploying its private storage/runtime and activating it waits for the owner's selected identity/secret boundary; no endpoint or credentials are invented here.

## Health, rotation and revocation

Existing observer health/backoff already classifies missing credentials, 401, rate limits, expired Gmail history and transport failures. Credential metadata health checks should expose presence and expiry only; they must not read plaintext into reports. On revoke, disable the affected observer/credential reference, cancel pending reads, keep cursors/evidence and classify the precise owner action. On rotation, swap the Vault secret atomically and verify one allowed read; do not rewind cursors or re-send events.

Blocked credentials do not prevent free purchase verification, the state audit, receipt projection, GitHub public observation or dependency readiness. Those continue through the existing supervisor.

Sources: https://api-docs.render.com/reference/authentication ; https://render.com/docs/api ; https://developers.google.com/workspace/gmail/api/auth/scopes ; https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.threads/get ; https://developers.google.com/workspace/gmail/api/auth/web-server .
