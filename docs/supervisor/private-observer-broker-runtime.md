# Private observer broker — deployable owner boundary

## Status and architecture

This supersedes the deployment gaps in observer-activation-readiness.md. The
standalone `private_broker.runtime:production_app` ASGI factory and Dockerfile are
ready for an **owner-created separate runtime**. Nothing is provisioned by this PR;
Render/Gmail activation remains false. Production-secret tests use fakes only.

The image copies only `private_broker` and the provider filtering library. It does
not include Jarvis, task executors, connector sessions or the Supabase worker. The observer harness is also excluded from the image.
Deploy it in a NEW owner-controlled GCP project, with a dedicated service account,
Firestore Native default database and four Secret Manager secrets. Jarvis/Actions
must have **no IAM role, project access, image-deploy permission or Secret Manager
access** in that project. Neither the runtime identity nor its project grants access
to the existing DUFYND Supabase service-role or management credentials.
Do not connect the private project's deploy identity to Jarvis's GitHub identity.
The existing Render API deployment is NOT the broker runtime.

The HTTPS listener is publicly reachable for Google callback, but all reads require
application-verified GitHub OIDC and all owner mutations require a different private
owner key. This is an application security boundary, not a private network listener.
Owner must audit platform logging before consent: no request bodies, query strings,
authorization headers, exception locals or debug logging may be retained/exported.
Consent start is blocked until BROKER_CALLBACK_LOGGING_READY=1 is explicitly set
after that audit. Uvicorn access logging and Python library logging are disabled; error responses contain fixed reason codes.
Create Logs Router exclusions on ALL project/organization sinks that could retain
Cloud Run request entries for `/oauth/gmail/callback`; Google authorization codes
and state arrive in the URL. If inherited logging cannot be excluded, do not run
consent on this deployment. Exclusion does not erase already-ingested logs.

## Authentication and exact endpoints

Observer identity is accepted only with a verified RS256 signature from fixed
`https://token.actions.githubusercontent.com/.well-known/jwks`, issuer
`https://token.actions.githubusercontent.com`, audience equal to BROKER_ORIGIN,
repository `tncommerce/commerce-agents`, immutable repository_id `1367576041`,
ref `refs/heads/scentai-mvp`, exact workflow_ref
`tncommerce/commerce-agents/.github/workflows/dufynd-private-observer.yml@refs/heads/scentai-mvp`,
subject `repo:tncommerce/commerce-agents:ref:refs/heads/scentai-mvp`, event
workflow_dispatch/schedule, valid exp/iat/nbf and at most ten-minute lifetime/age.
General GitHub identity, pull-request/fork identity and Jarvis workflow identity are
rejected. Arbitrary JWT key URLs are rejected. JWKS failure fails closed.

The dedicated workflow is manual and disabled unless
`DUFYND_PRIVATE_BROKER_ENABLED=1`. Its only configuration is the non-secret origin.
It has contents:read and id-token:write; **no upstream or management secrets**.
It reads fixed endpoints and emits filtered JSON, not raw provider responses.
It does not acknowledge cursors or enable observers. Scheduled Supabase SQL cannot
mint GitHub OIDC. Use this exact workflow as the bridge; add its owner-approved
schedule only after production acceptance. No fallback master token is provided.
For a future non-Actions observer, prefer a separately allowlisted short-lived
signed workload identity with distinct issuer/audience/subject and read-only policy;
implement and test that policy before enabling it, rather than sharing owner-key.

Allowed workload endpoints:

| Method | Path | Output/purpose |
| --- | --- | --- |
| GET | /v1/health | Non-secret credential health only |
| GET | /v1/render/services/srv-dakpfrnf3r2c73dr3f20/deployments | deployment_id, service_id, commit_sha, status, timestamps |
| GET | /v1/gmail/threads/{registered-thread}/metadata | thread/history IDs, message IDs, dates, From, sanitized MIME type, delivery-failure flag |
| POST | /v1/gmail/threads/{registered-thread}/ack/{observation-digest} | Advance private cursor only after durable ingestion; idempotent ack |

Registered threads: 1a0f385ed98c6af8, 1a0f69c169fb928f, 1a0f6a90772a743d.
No query parameters or arbitrary provider URL/path are accepted on reads. All
upstream URLs are fixed. Render accepts only GET of the one service's deploy list;
redirects, settings, env, logs, deploy/restart and mutations are unavailable.
Gmail uses profile for account proof, history for local known-thread filtering,
and known-thread metadata with From/Content-Type only. No search, body, attachments,
send, drafts, label-management, modify or delete endpoints exist. SENT/DRAFT messages
and unknown threads are discarded before durable evidence.

Owner-only POST endpoints: `/owner/oauth/gmail/start`, `/owner/gmail/revoke`.
The public GET `/oauth/gmail/callback` requires private stored one-use state; it is
not an observer endpoint. Never give owner-key to Jarvis or Actions.

## Secret and storage contract

| Value | Permitted location |
| --- | --- |
| Render upstream account key | Secret Manager broker-render-key, private mounted file only |
| Google client secret | Secret Manager broker-google-client-secret, private mounted file only |
| 32 random bytes, base64 encoded AES-GCM key | Secret Manager broker-encryption-key only |
| Random owner administration key (at least 32 characters) | Secret Manager broker-owner-key and owner's local password manager only |
| Gmail access/refresh tokens, PKCE verifier, expected mailbox | AES-GCM encrypted Firestore broker documents in private project |
| Provider/resource/scope references, status, expiry, refresh time, sanitized reasons | Existing non-secret Supabase credential metadata |
| Filtered known-thread/deployment evidence and dedupe IDs | Existing observer ingress/task control plane |

No secret belongs in git, task tables/packets, evidence, logs or chat. Secret
reference strings in the control plane are compatibility identifiers, not permission
to place upstream keys in Supabase Vault. The broker never holds a Supabase key.
Runtime IAM: datastore.user in **this private project only**; Secret Manager accessor
on only the four named secrets. No project editor/owner, IAM administration or
service-account token-creator roles. Disable public Firestore client access with
Firestore rules; REST uses the dedicated runtime's metadata-server identity.
Restrict project membership and deployment rights to owner/security administrators.

Firestore document `updateTime` / exists preconditions implement CAS. Every
credential mutation checks owner lease, non-expired 90-second lease and generation.
Concurrent refresh fails boundedly with refresh_race; provider exchange retries
exactly twice only for transient failures. Tokens and health rotate atomically.
An abandoned lease expires; an old holder cannot commit after takeover. Revoke
clears encrypted credential material and increments generation before upstream
revocation. invalid_grant invalidates the grant without retry. New refresh tokens
returned by Google replace the old token atomically. Re-consent uses the current
generation and invalidates older consent sessions.

OAuth uses fixed `${BROKER_ORIGIN}/oauth/gmail/callback`, PKCE S256, server-generated
one-use state (ten-minute TTL, consumed before exchange), offline access,
include_granted_scopes=false and exactly gmail.metadata. The stored verifier is
submitted only to Google's fixed token endpoint; Google rejects mismatch.
Returned bearer/expiry/scope and Gmail-profile mailbox must pass before persistence.
No access token, refresh token or authorization code is returned to the browser.
Google's external Testing refresh grants can expire after seven days; gmail.metadata
is restricted and production publishing/verification requirements depend on audience.
Resolve Google's requirements with the owner before unattended production use.

Encrypted records include a pending observation. Repeated read returns the same
unacknowledged observation. Authenticated ack checks digest and credential generation;
only then is the cursor committed. Partial history pagination/provider failure never
advances the cursor. At-least-once results are deduped by the existing control plane.
A stale history cursor fails closed; owner must explicitly reset/rebaseline it after
investigation. Expired/used OAuth records are inert but should be periodically purged
by owner-controlled maintenance; no paid Firestore TTL feature is required.

## Deployment recommendation and costs (checked 2026-10-02)

**A — Cloud Run request-based billing, scale-to-zero, separate GCP project**, with
Firestore and Secret Manager. Native runtime identity avoids stored cloud management
keys. Durable CAS supports multiple instances/restarts. HTTPS callback and cold-start
handling are built in. Template: private_broker/cloud-run.template.yaml; Docker build
context is repository root, Dockerfile private_broker/Dockerfile. Deploy a verified
image digest. No external git auto-deploy controlled by Jarvis.

Low-frequency polling is expected to stay near **US$0/month within available free
quotas**, not a guaranteed zero bill. Cloud Run free tier includes 2M requests;
Firestore Standard default DB offers 50k reads/20k writes daily and 1GiB storage;
Secret Manager offers six active versions and 10k accesses monthly per billing
account. Four mounted secrets fit if quotas are not consumed elsewhere. Image
registry/build storage, outbound traffic, additional secret versions, logs and quota
excess can incur costs. Billing account is required; budgets are alerts, not a hard
spend cap. Max instances=2 constrains compute but not abusive request cost.
Owner must approve project/billing before creation. No new budget is authorized here.

**B — Separate owner-controlled Render account/runtime plus private durable CAS
backend**, or an existing isolated server with an implemented durable backend.
Render is operationally familiar but paid Starter compute is about US$7/month;
persistent disk is US$0.25/GB/month extra. Free instances are not a durable secret
storage solution. Current production store adapter expects GCP metadata identity;
Render cannot run that adapter unchanged. A separately reviewed SQLite adapter with
single-instance persistent disk or private Postgres adapter is required before B is
deployable. Do not copy cloud service-account keys to Render as a shortcut. B has
more always-on cost and maintenance, and shared existing Render workspace administrators
would weaken isolation; use a genuinely separate owner account. A is deploy-ready
with the supplied adapter; B is the fallback architecture, not an implemented port.

Primary references:
- https://cloud.google.com/run/pricing
- https://cloud.google.com/firestore/pricing
- https://cloud.google.com/secret-manager/pricing
- https://docs.cloud.google.com/firestore/docs/reference/rest/v1/projects.databases.documents/patch
- https://docs.github.com/en/actions/reference/security/oidc
- https://developers.google.com/identity/protocols/oauth2/web-server
- https://developers.google.com/workspace/gmail/api/auth/scopes
- https://api-docs.render.com/reference/authentication
- https://render.com/pricing
- https://render.com/docs/disks

## Tuan's exact setup order — STOP before owner provisioning

1. **PRIVATE BROKER:** Owner creates/chooses an isolated GCP project/account and
   explicitly accepts billing; create Firestore Native default DB, Secret Manager,
   Artifact Registry and Cloud Run. Create broker-runtime service account with the
   above limited roles. Apply callback logging exclusions before any consent. Build
   and deploy the isolated image by digest; use min=0, max=2, request billing. Record
   the actual HTTPS origin assigned by Cloud Run; configure BROKER_ORIGIN to that
   origin, BROKER_PROJECT, BROKER_MAILBOX, GOOGLE_CLIENT_ID and immutable repo ID.
   No final URL exists before owner deployment; do not invent one.
2. **RENDER:** In Render Account Settings > API Keys, prefer a dedicated owner
   automation identity with minimum workspace memberships. Account keys may grant
   broad workspace/account access. Store its key only as broker-render-key. Never
   display/copy it in chat or Jarvis/Supabase. Pin its secret version in the template.
3. **GMAIL:** In the owner's isolated Google Cloud OAuth project, enable Gmail API;
   configure Google Auth Platform audience/test user as appropriate; create Web
   Application OAuth client. Register the exact redirect
   `ACTUAL_HTTPS_ORIGIN/oauth/gmail/callback` (no trailing slash). Request only
   `https://www.googleapis.com/auth/gmail.metadata`. Put client secret in
   broker-google-client-secret and public client ID in runtime config. Owner securely
   generates encryption-key and owner-key and stores them in the private project;
   neither goes into GitHub secrets. Mount version-pinned secrets using template.
4. Owner invokes POST `/owner/oauth/gmail/start` using the private owner-key from a
   local secure client, opens the authorization URL and consents once as the selected
   mailbox. Refresh token is captured/encrypted automatically; never show it or the
   client secret in chat. State/code URLs must not be pasted into task packets/chat.
5. Only after deployment, set non-secret DUFYND_PRIVATE_BROKER_ORIGIN in repository
   variables. Enable the fixed workflow for acceptance only. Workmode verifies health,
   real exact Render read, a known Gmail metadata read, duplicate delivery/ack and
   denied operations. Owner may rotate Render/owner/client secrets by creating new
   Secret Manager versions and redeploying pinned versions. Client-secret change
   requires re-consent so private token state is updated. Encryption-key replacement
   requires an owner-only offline re-encryption migration; never overwrite it while
   ciphertext exists. Do not rotate a master key blindly.
6. Existing trusted ingestion worker (outside broker image) projects only the existing
   RPC fields: discard message content_type if calling today's strict
   capture_dufynd_broker_observation contract. Copy non-secret health only, then ingest
   filtered evidence through that RPC. Ack only when accepted=true AND durable inbox/
   dedupe commit has succeeded; never ack rejected/disabled ingress. Enable observer
   rows and credential activation only after owner acceptance. Verify task wake,
   dependency processor and production smoke. The manual harness deliberately does
   not do any of these activation writes.

Remaining acceptance gaps are actual project IAM/logging audit, real Google consent
and policy status, real Firestore/HTTPS provider integration, and post-setup observer
activation. Mocks/CI cannot certify owner configuration. No credentials, external
account, paid service, budget, outreach or social publish is created by this change.
