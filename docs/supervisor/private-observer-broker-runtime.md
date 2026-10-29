# Private observer broker — deployable owner boundary

## Status and architecture

The standalone `private_broker.runtime:production_app` ASGI factory and Dockerfile
form the separate owner-controlled provider boundary. Repository source does not
establish the live deployment or activation state; verify those in the existing
runtime and masterstatus. Production-secret tests use fakes only. The explicitly
gated two-service extension is described in [render-services-v2.md](render-services-v2.md).

The image copies only `private_broker` and the provider filtering library. It does
not include Jarvis, task executors, connector sessions or the Supabase worker. The observer harness is also excluded from the image.
Use the verified existing owner-controlled GCP project, dedicated service account,
Firestore Native default database and four Secret Manager secrets. Do not create
a replacement project or resources as a recovery shortcut. Jarvis/Actions
must have **no IAM role, project access, image-deploy permission or Secret Manager
access** in that project. Neither the runtime identity nor its project grants access
to the existing DUFYND Supabase service-role or management credentials.
Do not connect the private project's deploy identity to Jarvis's GitHub identity.
The existing Render API deployment is NOT the broker runtime.

For the final broker service, allow unauthenticated Cloud Run **transport invocation**
(service-level allUsers/run.invoker only), because Google callback and raw GitHub
OIDC are validated inside the app. Do not grant public Firestore or Secret Manager
access. The HTTPS listener is publicly reachable for Google callback, but all reads require
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
repository_owner_id `324597697`, subject `repo:tncommerce@324597697/commerce-agents@1367576041:ref:refs/heads/scentai-mvp`, event
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

V2 adds only the two fixed Render deployment-list paths under `/v2/render/`,
disabled unless the explicit owner runtime gate is enabled. It has its own
per-service evidence and capture scope; the v1 metadata and API-only endpoint
remain unchanged. See the [versioned contract and rollout](render-services-v2.md).

Registered threads: 1a0f385ed98c6af8, 1a0f69c169fb928f, 1a0f6a90772a743d.
No query parameters or arbitrary provider URL/path are accepted on reads. All
upstream URLs are fixed. The v1 Render endpoint accepts only GET of the API service's deploy list;
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

## Owner deployment helper

Use the existing owner-controlled deployment environment and supply the verified
target explicitly. The helper has no project, region, service or registry default:

```bash
bash scripts/deploy_dufynd_private_broker.sh \
  --project "$VERIFIED_PROJECT_ID" \
  --region "$VERIFIED_REGION" \
  --service "$VERIFIED_SERVICE" \
  --image-repository "$VERIFIED_IMAGE_REPOSITORY" \
  --expected-origin "$VERIFIED_SERVICE_ORIGIN" \
  "$APPROVED_COMMIT_SHA"
```

`VERIFIED_IMAGE_REPOSITORY` has the form
`LOCATION-docker.pkg.dev/PROJECT/REPOSITORY/IMAGE`, without a tag or digest. Its
project must equal the explicitly supplied project. The origin is the existing
Cloud Run `status.url`, not an inferred project name or arbitrary callback URL.
In particular, the former hardcoded `dufynd-private-broker-01` is no longer used.

Before clone, build or push, the helper reads narrowly projected metadata for the
existing active project, standard Docker registry repository, service and ready
revision. It verifies project/namespace, region, origin, resource UID/version,
completed reconciliation, the existing image repository and resolved digest. It
requires the broker's single-container configuration and an existing 100%-to-latest
traffic policy, so the later image-only update needs no routing change. A wrong,
unreadable, missing or unready target stops before those operations. No IAM or
Secret Manager read operations are added. `--format` is a client-side output
projection, not a server-side field mask: environment and secret fields are
excluded from the emitted and temporarily saved metadata. The explicit
`spec.template.spec.containers[].image` slice preserves the container array while
omitting its other fields; this shape was verified offline with Google's official
SDK Core build `20261026202537`, including an excluded environment-value canary.

The owner environment also requires Docker buildx, checked before any build or
push. A pinned service image can identify an OCI index or Docker manifest list
while Cloud Run's ready revision identifies its `linux/amd64` image. For that
case, the helper reads the exact digest from the already bound repository with
`docker buildx imagetools inspect --format '{{json .Manifest}}'`, using existing
registry authentication. It checks the returned root digest, schema and media
type and requires exactly one supported `linux/amd64` child. Missing, duplicate,
foreign or ambiguous evidence fails closed; an attestation descriptor is not a
runtime image. No digest comparison is skipped.

It then checks out the exact immutable commit, builds and pushes the commit-tagged
image and verifies both the registry's SHA-256 digest and its fully qualified image
identity. The service UID/version/revision/image are checked again after build and
immediately before update. The pushed digest's runtime child is resolved before
the update as well. The sole Cloud Run mutation remains `services update
--image=IMAGE@sha256:…`; no IAM, secrets, environment, ingress, scaling, traffic or
resource-creation operations are added. The user's gcloud default project and
Docker authentication configuration are never changed.

Final verification binds **all** positive traffic to the specific ready revision,
checks that it is also the latest created revision and verifies its exact resolved
image digest. Reading only `traffic[0].percent` is insufficient. Bare SHA-256 values
and fully qualified digest references are normalized only for the explicitly bound
image repository; a foreign image with the same hash is rejected. Metadata-readback
checks are not an atomic lock against another owner deployment, so the existing
owner deployment channel must serialize updates to this service. A verification
failure exits without a success claim or automatic rollback; an image update that
already completed is not silently undone.

The final proof reports both `verified_image` (the pinned registry image or index)
and `verified_runtime_image` (the resolved image actually reported by the ready
revision). These may legitimately differ only through the verified registry
index relationship. The runtime source SHA remains the explicit helper argument;
an operational-helper correction does not require rebuilding from a different
application commit.

This flow follows the primary Google contracts for
[Artifact Registry image digests](https://docs.cloud.google.com/build/docs/securing-builds/generate-validate-build-provenance),
[Cloud Run service status and resolved traffic targets](https://docs.cloud.google.com/run/docs/reference/rest/v1/namespaces.services),
[revision imageDigest](https://docs.cloud.google.com/run/docs/reference/rest/v1/namespaces.revisions),
and [resource identity/version](https://docs.cloud.google.com/run/docs/reference/rest/v1/ObjectMeta).
The index handling follows the [Cloud Run container contract](https://docs.cloud.google.com/run/docs/container-contract)
and [Docker's manifest inspection contract](https://docs.docker.com/reference/cli/docker/buildx/imagetools/inspect/).

The helper still requires existing owner-authenticated GCP and Docker registry
access, plus independently verified available capacity under the standing **zero
additional cost** constraint. It does not verify billing headroom, infer a zero
bill from a free-tier label or start login/configuration flows. No deployment is
performed by the repository change or its subprocess tests. Jarvis/GitHub Actions
must not receive these GCP deployment credentials. Execution remains unavailable
in the current work session until an existing authenticated deployment channel and
the actual target/cost conditions are evidenced; no new approval dialog is implied.

## Separated ingestion and acknowledgment preparation

The acceptance handoff is split so no process needs both the Supabase service-role
credential and a broker workload token. `scripts/dufynd_private_observer_ingest.py`
is the trusted control-plane side: it accepts only the fixed filtered artifact
paths plus a strict source manifest, requires that manifest to match the same GitHub
run ID and commit SHA supplied by the trusted orchestration job, projects non-secret
health, strips broker-only Gmail `content_type`, commits the fixed Render/Gmail
evidence through the service-role RPCs and writes `broker-acks.json` only after all
four captures return `accepted=true`.

The source manifest is generated before the broker read from GitHub's immutable
workflow context and fixes repository/repository-owner IDs, integration ref, exact
workflow ref, event, commit SHA, run ID and run attempt. An artifact from another
run/ref/repository is rejected before any Supabase write. The resulting ack plan is
version 2 and carries the same source manifest.

`private_broker/observer_ack.py` is the complementary OIDC-only side. It accepts
only version 2 plans containing that same source manifest, exactly the three
registered thread IDs and 64-character observation digests. The source run ID/SHA
must match the current acknowledgment job before it mints the fixed GitHub workload
identity. It acknowledges only those exact broker paths and then requires a second
pass to return `duplicate` for all three digests. It has no Supabase, provider or
owner credential.

These helpers are preparation only. They are not yet wired into the workflow and
credential activation remains false. Production wiring must keep the credential
separation at job/runtime boundaries and must not enable activation until the real
broker read/health acceptance has passed.

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

## Historical initial-provisioning reference

The following records the original setup procedure, not the recovery procedure
for the existing broker. Use the verified existing owner runtime and the staged
[v2 rollout](render-services-v2.md) for this extension. Do not repeat provisioning,
accept billing or restart paused Gmail consent to resolve a Render read gap.

1. **PRIVATE BROKER:** Owner creates/chooses an isolated GCP project/account and
   explicitly accepts billing; create Firestore Native default DB, Secret Manager,
   Artifact Registry and reserve a Cloud Run service/HTTPS origin using an owner-only
   private bootstrap revision without broker credentials if the provider requires a
   revision before assigning its URL. Record that actual URL before configuring the
   OAuth client. Create broker-runtime service account with the above limited roles.
   Apply callback logging exclusions before any consent. Build the isolated image by
   digest; configure BROKER_ORIGIN to the assigned origin, BROKER_PROJECT, selected
   mailbox and immutable repo ID. Finish steps 2–3 before deploying the real broker
   revision with its required mounted secrets and GOOGLE_CLIENT_ID. Use min=0, max=2,
   request billing. Only then allow unauthenticated transport on this broker service;
   application authentication remains mandatory. No final URL exists before owner
   project/service creation; do not invent one.
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
   capture_dufynd_broker_observation contract. The read harness snapshots `/v1/health`
   only after its fixed Render/Gmail reads, then a trusted service-role worker may call
   `project_dufynd_broker_health` with that exact bounded health object. The projection
   validates the canonical provider/resource/scope contract, rejects stale health and
   extra fields, and **never changes activation_enabled**. Ingest filtered evidence
   through `capture_dufynd_broker_observation`. Ack only when accepted=true AND durable
   inbox/dedupe commit has succeeded; never ack rejected/disabled ingress. Enable
   credential activation only after owner acceptance. Verify task wake, dependency
   processor and production smoke. The manual read harness deliberately does not make
   Supabase writes or activation writes.

Remaining acceptance gaps are actual project IAM/logging audit, real Google consent
and policy status, real Firestore/HTTPS provider integration, and post-setup observer
activation. Mocks/CI cannot certify owner configuration. No credentials, external
account, paid service, budget, outreach or social publish is created by this change.
