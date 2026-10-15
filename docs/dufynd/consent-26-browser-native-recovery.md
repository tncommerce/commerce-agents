# CONSENT-26: actual browser evidence and bounded integration correction

Status: CORE_BROWSER_EVIDENCE_PASS_ON_PARENT / CORRECTIONS_TESTED_IN_VM /
FULL_INTEGRATION_OPEN / NO_RELEASE.
Parent: bf45ff368bbdf0d93a7d4312e1d5bab9c9ba8a17, PR #794.

## Evidence independently read, not a whole-CI PASS

GitHub Actions 38728501615 is FAILURE on this parent. The authentic partial
artifact 11968703997 (34869692 bytes, 84 ZIP entries) was downloaded, its SHA-256
3814e2c81428973f17f4f1b040c397eb6c3166b7fd899e8a752a45dffe2d5e03
and ZIP CRC verified, and the actual reports inspected.

`consent26/report.json`: PASS, seven actual Chromium scenarios. Four widths
320/390/768/1440 pass default off, explicit choice, withdrawal, denied reload and
merchant href availability (no merchant click). Additional cross-tab withdrawal,
in-flight withdrawal and blocked-preference-storage cases pass. The report
records zero external requests and zero actual merchant clicks. This is real
browser execution of those scenarios, not a full-site release, real iOS/Safari
result or legal consent certificate. These are parent-build results; later
changed code still needs new exact-tree browser verification.

The larger report remains incomplete/failed: 142 checks, 126 passed and 37
reported failures including asynchronously collected suite failures. Many older
positive attribution fixtures still assume implicit analytics or advisor identity;
several interactions are intercepted by the undecided preference panel. They
must be migrated deliberately, not auto-granted by production code or deleted.
Four catalog checks also expose raw fragment-anchor rewriting, addressed below.

Python 3.12 reported 11 failed, 3442 passed, 202 skipped and 28 setup errors.
Those 28 errors share one test-fixture cause: iterating app.routes accessed
.path on an included-router container. They do not establish 28 application bugs.

## Actual code changes in this correction

1. The native ASGI fixture now selects APIRoute instances only, requires exactly
   one matching route with the actual analytics_event function and exactly one
   record dependency. It still overrides only the test functional session and
   synthetic stores. Consent gates, middleware and endpoint bodies are unchanged.
   All 28 scenarios and all network-blocking checks remain.
2. The five existing positive redirect-correlation tests (four functions, one
   parameterized) now declare measurement=granted-v1 at their direct endpoint
   calls. Destination, idempotency, reference and persistence assertions remain
   byte-for-byte. Ungranted/invalid cases remain in the actual ASGI suite.
3. The bounded-session structural test checks the current generation-owned
   pending initializer and its late-callback gate, instead of an obsolete literal
   assignment. Transport timeout and browser-recovery coverage checks remain.
4. The actual client helper preserves same-document #fragment anchors without
   consent/storage reads or attribution. Other relative/query-only targets resolve
   against the current document, not the origin root. Withdrawal strips optional
   fields only when present; it no longer rewrites clean raw anchor attributes.
   Native navigation uses the anchor's raw href before resolving it. The strict
   external/API destination boundary remains and no test is allowed to opt in
   using qa=1 or a copied measurement query.

The fragment defect is reproduced on the exact parent source:
appendAcquisitionAttribution('#duftkatalog') wrongly returned the site's root URL
plus the fragment. This is an actual navigation/serialization defect, not a reason
to remove the catalog CTA assertion.

## Local evidence actually executed for changed client code

- New test-measurement-anchor-navigation.mjs: 24 cases PASS across unknown,
  denied and granted states, relative/query-only destinations, untouched foreign
  URLs, raw fragment preservation and withdrawal of decorated clickout fields.
- Exact unchanged parent analytics source fails this same suite on the first
  fragment case. No production or network mutation in either control.
- Existing test-measurement-consent.mjs rerun on corrected analytics:
  18 scenario groups and 213 combined boundary cases PASS, no real requests.
- Production analytics blob d4b5e914d3489bafcd005af4361fac9122749432 and test blob
  93177de77efc30ea9eeea16ffbd30df5f9c16862 match the locally executed files.
- Test VM helper a13428db84318ec4911fefe9bd01388d926b59a3 only exposes its existing
  synthetic document so anchor mutation can be asserted; permission logic is real.

Full native-host pytest execution of the corrected fixture was not available in
this local environment; its result must come from the new repository CI. Do not
report those 28 corrected test setups as 28 newly passed tests in advance.

## Remaining work, no false overall finish

Migrate the remaining positive browser fixtures to a deliberate choice and the
independent measurement identity, including telemetry query matching; keep the
unseeded default/deny/withdraw scenarios independent. The existing repository
source-evidence window packing and quote assertions also need a bounded update
for the changed consent-aware source; do not enlarge budgets or invent citations.
No provider run or production task is needed to fix those offline tests.

Signed/server-revocable evidence for previously copied granted URLs, actual
retention/deletion, provider agreements, image rights and final full browser/CI
acceptance remain open. No schema mutation, production merge, real affiliate click,
spending, new Nightshift, external message or source image change in this commit.
