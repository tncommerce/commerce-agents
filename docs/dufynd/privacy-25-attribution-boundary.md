# DUFYND PRIVACY-25 — outbound attribution boundary

Date: 15 October 2026. Isolated development only. Base: WOW24 PR #792,
`fa2081692e10764af619b085febca077b18f494f`. The green WOW24 branch is unchanged.
No production release, database migration, consent approval or general legal-compliance claim.

## Reproduced defect and implemented correction

The actual exported `appendAcquisitionAttribution` helper enriched any parseable
URL with acquisition/session fields before checking the destination. The new
isolated test fails on the pinned original: an unrelated `https://other.test/source`
receives `src`, `cmp`, `content` and a synthetic `sid`. This demonstrates the helper
behavior, NOT evidence that a real person's data was actually transmitted.

The destination check now runs BEFORE acquisition capture or storage access:

- Same-origin HTTP(S) storefront navigation retains existing attribution.
- The separately configured DUFYND API is permitted only at its exact origin and
  clickout path for one valid offer segment. Same-origin `/api/clickout/<offer>`
  is also supported. Arbitrary endpoints and lookalike hosts are not approved.
- Unrelated origins, credentials in URL authorities, non-HTTP schemes, malformed
  URLs, encoded path separators and invalid offer paths are returned unchanged.
  This helper does not navigate, authorize unsafe links, or remove pre-existing
  third-party tags. It only refuses to add DUFYND data.
- Rejected destinations do not capture acquisition data, read/write browser
  session storage, initialize a session or send a request through this helper.
- Allowed destinations retain query/fragment, campaign continuity, internal-QA
  markers, blocked-storage behavior and the existing advisor session ownership.
- Server-side rendering returns the original href without enrichment.

This is a bounded data-minimization correction. It does not create a second
analytics pipeline, alter prices/SKUs/image rights, or change the website layout.

## Evidence actually executed

`node scripts/test-attribution-boundary.mjs` compiles the ACTUAL analytics.ts using
the existing TypeScript dependency and runs it in isolated Node VM fixtures.

- 105 cases PASS on the corrected source.
- The same suite fails on the exact baseline at the first unrelated origin.
- Baseline source blob checked: `688b7e4151f0a8cee2547beae6223d5fbd5d4d00`.
- Corrected source blob: `b5f577f8df42bcb3f73d2f915cfd739cc0586fd9`.
- Test script blob: `f7681da73a542a460985e8af7fbafaa7aa43cef0`.
- Network requests and production mutations: zero in these tests.

The test is wired into the existing storefront prebuild. No dependencies or
workflow permissions changed. Full exact-head CI and existing browser/funnel
regressions still have to pass; the local VM proof is not a browser, deployment,
real visitor, real merchant click or commission receipt.

## Remaining privacy implementation — not closed by this patch

1. Consent and withdrawal: the current base still captures attribution and
   analytical sessions and sends first-party telemetry without a consent state in
   this helper. Define and implement the required default, explicit choice,
   withdrawal, queued/in-flight event cancellation, storage cleanup and URL
   identity handling consistently. Preserve shopping without optional analytics.
   Do not claim that restricting destinations resolves the consent question.
2. Retention/deletion: actual database and fallback-log lifetimes must be
   evidenced and a bounded deletion implementation prepared. No duration is
   invented here; no production data or cron is changed.
3. Provider agreements/regions/transfers and the legal assessment remain explicit
   release gates. BUSINESS-20 privacy text is a description, not approval.
4. Before release, verify ordinary external reference links, same-origin UI,
   separate-origin configured API clickouts, native keyboard/new-tab navigation
   and existing attribution tests in the assembled build. No real clickouts.

## Rabanne image workstream

Continue the existing PHOTO-14 decision for Rabanne 1 Million EDT 100 ml,
GTIN 3349666007921. The known merchant-bound review image is not a transferable
Perfumetrader permission. No image substitution or repeated Commons research.
A read-only search of the connected mailbox for Awin/Perfumetrader messages after
14 October found no new message establishing the missing permission. This is
limited to that mailbox, not proof that the Awin platform has no media.
A fresh authenticated asset plus exact usage terms remains the required source.
No email sent, login challenge retried, paid API used or image published.

## Release and rollback

This patch belongs on `dufynd-privacy-25-20261015`, stacked on the existing WOW24
branch. Never merge into `main` or `scentai-mvp` without separate exact Owner GO.
The change is reversible as a single commit; no schema/data migration is involved.
The original green WOW24 commit is retained as the reference. Missing Awin
transactions remain UNKNOWN revenue, not an automatic prohibition on a later
otherwise-approved website release. No new Nightshift or social-content work.
