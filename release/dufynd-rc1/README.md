# Rabanne RC1 — base-bound development artifact

Not a publication authorization. Do not merge PR #774 to release this candidate.

`manifest.json` binds `candidate.patch` to integration commit
`86d58bee958cade3ef372ddeaa6d9cf5baaa003e` and its exact candidate tree.
Only three storefront files change: existing product route, existing offer
component, and route-scoped CSS. No review routes, private photo modules, new
catalog projections, data changes, package changes or migrations are included.

The existing base architecture, API, offer freshness/eligibility checks, analytics
and attribution remain authoritative. The public Rabanne route explicitly holds
all product-photo surfaces including metadata, gallery and 3D; no image permission
is inferred. Other product routes do not opt into the new presentation. Existing
non-Rabanne data and presentation are inherited unchanged, not newly audited or
approved by this candidate. Product metadata is not a current offer quote.

## Reproduce

Run from the development checkout with Node 22, Git and the base object available.
Use a new disposable absolute `CANDIDATE` directory outside this checkout and an
`EVIDENCE` directory. No branch/ref or candidate commit is created.

1. `node release/dufynd-rc1/verify.mjs prepare "$CANDIDATE" "$EVIDENCE"`
2. In `$CANDIDATE/examples`, install locked dependencies with `npm ci`, then run
   `npm run build --workspace acme-retail-storefront-web` (includes all base prebuild checks).
3. `node release/dufynd-rc1/verify.mjs export "$CANDIDATE" "$EVIDENCE"`
4. Install Playwright 1.55.0 without saving and its Chromium browser in this
   disposable candidate. Copy `browser-qa.mjs` into `$CANDIDATE/examples/` for module
   resolution. Serve the candidate's static `out` with its existing server, then
   invoke the copied runner with local base URL, candidate path, evidence path and
   the absolute `observed-offer.json` path.
5. `node release/dufynd-rc1/verify.mjs rollback "$CANDIDATE" "$EVIDENCE"`

The rollback verifier reverses the patch in the actual detached source worktree,
checks exact base-tree equality and then reapplies it for review. This proves
source reversibility; it performs no production deployment rollback.

The existing CI workflow has a candidate-only job using the same entry triggers
and read-only contents permissions. It builds and tests the three-file candidate
independently of the rest of PR #774, preserving existing CI jobs and tests.

## Evidence semantics

`observed-offer.json` replays the unchanged public API observation from
2026-10-12 10:49 UTC, whose offer record timestamp is 2026-10-10 19:56 UTC.
Its 71.90 + 4.99 = 76.89 EUR is historical browser-test evidence, not a new current
price check. The browser intercepts it through the existing offer fetch path.
Artificial 90 + 5 EUR cases test retry, unknown shipping and comparison separately.
Neither fixture is copied into public assets. All external requests are blocked;
merchant links are inspected but never clicked. Analytics are intercepted.

CI artifacts include the patch/manifest, production build, build log, source/export/
rollback JSON, candidate-only browser results and 390/1440 px offer/error/empty
screenshots. A candidate tree hash is distinct from the development packaging
commit. Technical preparation does not authorize merge/deploy or certify 9.5/10
premium quality. A licensed Rabanne original photo remains absent.
