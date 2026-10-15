# CONSENT-26: first native browser and API-host integration

Status at commit: SOURCE_INTEGRATED / NATIVE_EXECUTION_PENDING / NO_RELEASE.
Parent: a00ea994519569cf0affe483bbf7e7c99f5a5aee.
Existing branch: dufynd-consent-26-20261015.

## New executable coverage

The default pytest run now collects tests/test_dufynd_measurement_host.py.
It imports the actual retail.api.main.app and sends HTTP requests using
httpx.ASGITransport. The actual routing, parameter/Pydantic validation,
background tasks and middleware run. The functional session dependency and
merchant stores are explicitly synthetic. Both redirect URL builders remain
real. Analytics/clickout writes use in-memory spies. External HTTP transports
raise, and redirect following is disabled. None of these are real merchant visits.

Coverage includes absent/invalid grant with QA and copied identity fields,
both legitimate redirect paths with an explicit declaration, no-storage event
responses, unavailable/hidden product gates, request validation and local CORS.
A grant followed by an ungranted request must not keep recording. This is NOT
proof that a previously copied granted URL is server-revoked.

The existing analytics retry test receives an explicit grant on its three
positive calls. Its lost-response, idempotency, QA and cross-session assertions
remain unchanged. Denied cases are separate, not globally granted.

measurement-browser-qa.mjs is called by the existing pending-image CI entry point
before that existing regression. Its contexts start unseeded; it clicks the real
choice controls. It checks unknown/off, equal choice presentation, denial, grant,
withdrawal, reload, multi-tab withdrawal, attempted in-flight cancellation and
blocked preference storage. It verifies actual merchant hrefs but never follows
a merchant redirect. Remote requests are mocked or rejected. Screenshots and
report go to .visual-qa/consent26 inside the existing artifact path.

The existing four Rabanne/Delina x Instagram/TikTok first-money journeys now
explicitly choose analytics in the real UI, mock the exact new telemetry query,
and bind a stable independent measurement UUID across navigation. The previous
identity-equals-transport assumption is replaced with independence plus stability,
not omitted. Product, source, campaign, content and per-event transport checks,
and the deliberately never-completed image regression, remain.

## Evidence boundary

All five new/modified code files pass local Python AST / Node syntax checks.
Uploaded large blobs exactly match the locally checked bytes. The complete
repository/runtime dependencies are not installed in the main-chat container,
and the prior browser loopback policy restriction was not bypassed. Therefore
NO native ASGI, browser, full-build, visual-quality or full-CI PASS is asserted
in this commit. Those proofs are to come from the existing standard PR CI.

The previous client VM results (21 ownership / 213 boundary) are recorded in
consent-26-fixture-integration.md, not relabelled as native test evidence here.

## Remaining integration

Open the single CONSENT-26 draft PR against PRIVACY-25 for its FIRST actual full
application execution. Do not change CI permissions or add a duplicate pipeline.
Legacy browser regressions outside the migrated core funnel still contain old
implicit-collection/transport-ID assumptions. A diagnostic failure there is not
a release PASS and must be migrated with explicit positive and negative cases.
No test family, failing assertion or workflow is disabled to obtain a green run.

Server-side revocation/evidence for copied granted URLs, data retention/deletion,
provider agreements and factual privacy text remain open. The client declaration
is not a legal certificate. No production merge, data deletion, deployment,
Nightshift activation, new image right, spending or duplicate email is performed.
