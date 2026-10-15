# CONSENT-26: executable client-fixture integration

Status: CLIENT_FIXTURES_PASS / BROWSER_AND_API_HOST_INTEGRATION_OPEN / NO_RELEASE.
Source parent: `59f33decf70a66c6ca2e3b102fd15ef91d02570a`.
Development branch: `dufynd-consent-26-20261015`.

## Implemented change

The two existing prebuild suites now load the real `measurementConsent.ts`,
`acquisitionEntry.ts` and `analytics.ts` in one isolated VM/window per case.
The test-only `scripts/measurement-vm-fixture.mjs` supplies synthetic storage,
transport and DOM; it does not replace the consent decision or acquisition parser.
Its default is unknown/off. Positive suites explicitly call the actual setter.
Neither `qa=1` nor an incoming measurement query is used to manufacture permission.

The ownership suite preserves concurrent initialization, both advisor takeover
races, bounded retry, event idempotency, navigation, invalid/blocked storage,
referrer trust and QA classification checks. Identity expectations now require a
measurement UUID distinct from the advisor transport, stable through renewal and
consented document navigation. Five additional off/deny/revoke/SSR cases exercise
no transport initialization, no optional reads/writes, retained advisor ownership,
late callbacks, aborted requests and discarded queued events.

The boundary suite retains all 193 destination cases and adds 20 fresh/denied
cases. Both real redirect shapes, alternate API path roots, missing transport
sessions, blocked storage, existing query/fragment, fake origins, bad schemes and
invalid identifiers remain covered. Rejected destinations must not even read the
preference; allowed destinations without permission remain navigable without
optional identity/campaign fields. This checks generated links, not a live
merchant or the full browser application.

`test:measurement-consent` is also registered in the existing package prebuild.
No existing script or assertion family is disabled. No dependency, workflow,
application code, protected branch, credential or production data is changed.

## Actually executed in this main-chat runtime

- `node scripts/test-analytics-session-ownership.mjs`: 21 cases PASS.
- `node scripts/test-attribution-boundary.mjs`: 213 cases PASS (193 retained + 20 new).
- Red control: a separate temporary analytics copy omitting the configured
  merchant-partner route fails the migrated boundary suite.
- Red control: a separate temporary consent copy that trusts the incoming
  `measurement=granted-v1` query fails the migrated ownership suite.
- All three production source modules were byte-checked against the GitHub blobs
  before execution and are unchanged by this commit. No real network calls or
  production mutations occur in these fixtures.

Runtime inputs:
- analytics: `b4e06b214f75a495bb6f110294c62a7de2d679fb`
- consent: `7dcd27e98dd9a361f21149ed0001bafc1f3e7849`
- acquisition: `61668c8e1b88807679788377ba7b18b87fb72719`

This is new evidence for the migrated client integration, not another claim based
on the original package's 18 scenario groups. It is not a full build, browser QA,
ASGI-host run, field performance measurement or complete privacy/legal approval.

## Remaining bounded work

Client prebuild fixture migration (item 1 in `consent-26-integration.md`) is now
complete. Before opening the application candidate PR, migrate the browser mocks
to the actual telemetry query, explicitly grant only positive cases, and preserve
separate fresh/deny/revoke paths. The Python application-host fixtures still need
explicit consent for positive logging cases and unseeded negative coverage.

The actual consent UI and all shopping paths require rendered browser acceptance.
Previously copied granted URLs still have no server-side revocation receipt;
retention/deletion, provider agreements and factual privacy copy remain open.
Do not replace these remaining tasks with a green-parent or local-VM claim.
No full CI or public release was triggered by this fixture-only checkpoint.
