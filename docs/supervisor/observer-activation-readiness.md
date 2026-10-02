# Observer activation preparation — 2026-10-02

## Result and current boundary

The existing state audit/watchdog/event processor remain authoritative. Credential
metadata and health are now service-only non-secret contracts with exact provider,
resource, operation, scope and reference allowlists. Missing/expired/revoked or
mismatched configuration remains blocked_configuration, never an automatic
waiting_human_input. Only revoked/invalid_grant/wrong-account authorization calls
for explicit owner reauthorization. This does not create a business approval.

Direct Render/Gmail token HTTP is removed from the database poller. Public GitHub
observation is unchanged. Existing Render/Gmail observers receive filtered evidence
through capture_dufynd_broker_observation; their normalizer, inbox, dedupe, cursors,
review gates and dependency processor are reused. Ingress requires enabled
activation, current credential health (within five minutes), and an exact registered
source. Scope constraints reject broadened metadata. No actual secret is provisioned.

The Python preparation module implements fixed upstream paths, bounded response
reads, no redirects, exact service and thread checks, sender/delivery filtering,
foreign history discard, four-page bounded traversal with no partial cursor commit,
offline refresh, lock/CAS storage interface, atomic token+health rotation, account
validation via Gmail profile, precise failures and revocation. Refresh retries are
bounded to two transient attempts. Token/error bodies never enter evidence or logs.
No OAuth web server, callback, Vault backend or new service is deployed by this PR.
Mock storage is test-only and must never be used for production credentials.

The private broker must have a genuinely separate secret/storage boundary. The
existing trusted Actions service-role runner is not an untrusted agent sandbox;
placing refresh/client/Render upstream secrets in its task environment would defeat
the separation. The owner must choose the private broker runtime and a Vault backend
with distributed locking plus atomic generation checks. No new recurring cost is
accepted. A separate permanently running Render service has not been created.

## Exact owner steps: Render

1. Open https://dashboard.render.com and choose the TNCommerce workspace. Target
   only scentai-api, service srv-dakpfrnf3r2c73dr3f20.
2. Select a dedicated automation identity if Render permits it; otherwise open
   Account Settings > API Keys for an owner-authorized upstream key.
3. The worker needs only GET /v1/services/srv-dakpfrnf3r2c73dr3f20/deploys.
4. Official Render auth docs currently describe account keys covering all
   workspaces of the identity, not a native per-service read-only key.
5. Such a key has broader account authority; the broker, not its name, enforces
   our read-only exact-service restriction. A personal key must not go into Jarvis
   tasks or Supabase's observer access-token reference.
6. Enter the upstream key only in the selected private broker's provider/Vault
   secret UI. Keep its worker credential separately rotatable. The existing
   dufynd_observer_render_read_token is a reference, not permission to store a
   broad upstream key. Revoke upstream keys in Render Account Settings; disable
   credential activation and clear pending reads before rotation/revoke.
7. After the owner-selected boundary is implemented and provisioned: test one real
   exact deployment read, filtered event, SHA dependency wake and dedupe, plus
   denied other service/write/redirect calls. Then verify production smoke. We do
   not enable activation based on metadata alone.

## Exact owner steps: Gmail

1. Open https://console.cloud.google.com, select/create the DUFYND OAuth project.
2. Enable Gmail API in APIs & Services > Library. Configure Google Auth Platform
   branding/audience for the selected owner mailbox; add it as a test user when
   using external testing. Create an OAuth client of type Web application.
3. Request only https://www.googleapis.com/auth/gmail.metadata with offline access.
   Do not add gmail.readonly, send, modify or broad mailbox scopes.
4. Register the exact HTTPS callback of the selected private broker. No callback
   origin exists yet; do not register a made-up DUFYND/Render URL. The private web
   consent adapter must enforce fixed redirect URI, one-use state, PKCE, selected
   account and exact returned scope before accepting a refresh grant. Those web
   callback responsibilities remain an activation prerequisite, not a feature of
   the refresh-only module. Use include_granted_scopes=false to avoid combining
   older broad grants. If necessary revoke a prior broad grant first.
5. Complete the one-time consent while signed into the selected DUFYND mailbox.
   Account identity is checked using Gmail profile; profile values are not stored
   as general mailbox data. No credentials belong in chat.
6. Client secret and refresh token stay only in the private broker's Vault. Access
   rotation and health commit together under a durable lock/CAS generation. The
   Supabase metadata row stores only reference/scope/resource/health facts. The
   broker submits filtered known-thread evidence, never upstream credentials.
7. Revoke via the Google account's third-party access page and private broker
   revoke operation; disable ingress, invalidate storage generations and erase
   private credentials. Rotation requires an exact-scope/account-checked grant.
   invalid_grant disables the grant and requires owner reauthorization; no blind
   retries, mail send or rights approval. Later live acceptance covers registered
   thread metadata, new-message detection, dedupe and task review, without sending.

Google's external testing refresh grants may expire after seven days for this
scope; a test grant is not a durable production credential. Determine the owner's
internal/personal-use/production consent setup before claiming unattended uptime.
The scope is classified restricted, even though no message body is read.

## Remaining owner decision

Choose the private broker/Vault boundary or authorize its operating cost if needed.
Only then can exact callback, provisioning UI and deployed distributed storage be
specified and real credentials activated. Until then both providers intentionally
remain inactive; free internal/GitHub handlers continue.

## OPTIMIZATION_CANDIDATE

| Problem | Cause | Solution | Benefit | Risk | Priority |
| --- | --- | --- | --- | --- | --- |
| Repeated deployment owner checks | broad upstream Render authority | exact fixed-read broker plus existing event waits | remove manual SHA correlation | broker isolation must be real | P0 |
| Repeated credential polling failures | missing durable grants | metadata health and inactive broker state | no token attempts, precise setup blocker | stale health must fail closed | P0 |
| Gmail consent churn | external testing token lifetime | correct owner-specific consent lifecycle | durable metadata observation | restricted-scope policy/setup | P1 |
| Duplicate repair paths | audit/reconciler overlap | extend existing certified audit | reuse fencing/retry/leases | audit must not claim repair | Completed |
| Chat-context reconstruction | health scattered in task prose | bounded metadata and exact receipts | fewer context dumps | secret-like free text forbidden | P1 |

Sources checked 2026-10-02:
- https://api-docs.render.com/reference/authentication
- https://developers.google.com/workspace/gmail/api/auth/scopes
- https://developers.google.com/identity/protocols/oauth2/web-server
