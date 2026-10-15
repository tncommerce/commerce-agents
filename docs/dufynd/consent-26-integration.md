# DUFYND CONSENT-26 — versioned runtime draft

Status: DRAFT_RUNTIME_PRESENT / FIXTURE_MIGRATION_OPEN / NO_RELEASE.

## Recovered execution path

The owner cannot use Work mode and asked to continue in the main chat. A fresh
GitHub capability discovery exposed working Git-data write actions. Creation of
`dufynd-consent-26-20261015` from PR #793 head
`c662bbe83171e2fca3a80ac0f283e0262bdc3d5b` succeeded. No new owner permission,
credentials, paid service or alternate permission bypass was needed.

This branch imports the EXISTING hash-verified local CONSENT-26 package into the
actual storefront/API paths. It is not a reimplementation, a protected merge, a
new Nightshift or a deployment. The green PRIVACY-25 and WOW24 references remain
unchanged. No duplicate Perfumetrader email was sent.

## Modules and behaviour

`lib/measurementConsent.ts` owns the versioned preference (unknown means off),
expiry, storage failure and cross-tab/BFCache invalidation. The preference is not
a user ID. The 180-day preference lifetime is a draft product choice, not a legal
retention conclusion for collected analytics.

`lib/analytics.ts` uses that state before optional storage or transport, rotates
measurement identity independently of the functional advisor session, invalidates
queued generations, attempts to abort current analytics POSTs, and removes old
optional identity/link fields when permission ends. Existing strict target
boundaries for product and general merchant-partner redirects remain.

`MeasurementPreferences.tsx` and its CSS module are attached through RootLayout;
both choice buttons have the same styling. Settings and direct withdrawal remain
available. The UI has NOT passed rendered full-app/browser acceptance yet.

The actual three API endpoint bodies in `examples/retail/api/main.py` require the
explicit `measurement=granted-v1` transport declaration to write optional events.
Without it, valid merchant targets remain accessible without new DUFYND
measurement/clickout records or dynamically added DUFYND references. Redirects
are no-store/no-referrer. This does not disable an affiliate network's independent
processing or provide cryptographic proof of consent. Copied previously granted
URLs are not server-revoked by this draft; decide and verify that boundary before
claiming final consent/withdrawal readiness.

## Verified local evidence

The existing ZIP CRC and every supplied SHA256 entry were checked. The imported
runtime/test blobs match the original package hashes.

`node examples/retail/storefront-web/scripts/test-measurement-consent.mjs`
passed 18 behaviour scenario groups and 213 consent/URL-boundary cases on the
actual transpiled consent and analytics modules with synthetic DOM/API/storage.
`python tests/test_dufynd_measurement_consent.py` exercises 31 extracted-endpoint
cases with synthetic stores and compares the exact parent endpoint as a red
control. Pytest collects that grouped endpoint suite as ONE pytest test: do not
misreport 31 separately collected pytest tests. No real merchant or analytics
requests were made by these tests.

These local tests were rerun in the main-chat runtime, not inferred from an old
report. Native Chromium inspection of the local synthetic harness was attempted
but its initial loopback navigation was blocked by administrator policy. It was
stopped; no browser PASS or visual quality score is claimed and no alternate
navigation was attempted to defeat that restriction.

## Required integration still open

The old test fixtures assumed collection without a consent decision. They MUST
be migrated before treating this draft as an application candidate:

1. Existing analytics ownership/boundary VM tests must load the real consent
   module, explicitly grant positive cases, distinguish independent measurement
   IDs from advisor transport and retain unseeded denial cases. Do not use qa=1
   as a grant, or weaken an assertion merely to obtain green CI.
2. Existing browser API mocks must cover the new telemetry query. Use deliberate
   consent in positive tests and separate unseeded default/deny/revoke tests.
   Keep unexpected destinations blocked; never send QA to a deployed service.
3. Real API-host/ASGI tests must cover both redirect paths with and without a
   grant, expiry/availability, old URLs and current consent evidence. Extracted
   endpoint-body tests are not a full application or CORS result.
4. Verify functional advisor/bootstrap, library, search and merchant navigation
   without optional analysis, as well as stale anchors, multiple tabs, storage
   denial, queued work and late callbacks in the integrated browser build.
5. Update privacy copy to actual behaviour, verify retention/deletion and provider
   agreements, and bind the final release and rollback only after the code and
   factual/legal prerequisites are satisfied. A client flag is not a legal
   certificate; do not claim completed GDPR compliance.

No full CI is reported for this draft. No CI workflow or tests have been disabled.
The branch is being saved before PR creation so a known-unmigrated test suite is
not repeatedly dispatched. The repository CI still runs for protected pushes,
PRs and explicit dispatch as before. Finish the concrete fixture integration,
then open the draft PR and inspect its actual full CI/browser result here; Work
mode is not required. Never describe the green parent as proof for this new tree.
