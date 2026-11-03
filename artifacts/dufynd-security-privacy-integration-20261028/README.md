# DUFYND security/privacy integration — 28 October 2026

## Result

**New combined local integration PASS; production release remains HOLD.**

The production branch still points to `36cc84c34791284e4245ab4504ae020434dca89e`.
No production branch, Render deployment, Supabase schema or provider credentials
were changed by this verification. No GitHub CI was dispatched. Existing successful
178-page browser QA and the 163-case commerce suite were not repeated.

The isolated source tree combines exactly:

- [Security #840](https://github.com/tncommerce/commerce-agents/pull/840),
  `833feefcd6e4c525ef83fcd0a3a3f9f9b72629f3`: three dependency/lock files.
- [Privacy #823](https://github.com/tncommerce/commerce-agents/pull/823),
  `a9a8220d503d7db2bacfe1f4319188ca813878fa`: one offer-impression fix and seven QA files.

Both changes share the current production baseline and apply without conflicts.
The combined, pre-evidence Git tree is
`2dc1be16bed72993b437f9fbde513299d1e5d46a`, an **11-file delta** from production.
`evidence.json` records every changed file's Git blob and SHA-256. The evidence
directory itself is not part of that tested application tree.

## Reused evidence and its exact limits

| Evidence | Verified result | What it does not prove |
| --- | --- | --- |
| [#840 CI 40496435977](https://github.com/tncommerce/commerce-agents/actions/runs/40496435977) | Success on exact `833feefc`: six required jobs, including builds of every app | Its responsive-browser job was skipped; no Render deployment |
| [#840 preflight 40494772137](https://github.com/tncommerce/commerce-agents/actions/runs/40494772137) | Static build and **0** vulnerable production packages in the DUFYND storefront workspace; three file hashes match #840 | No all-monorepo security clearance; not current production |
| [#823 isolated QA 40645190771](https://github.com/tncommerce/commerce-agents/actions/runs/40645190771) | 178 responsive checks, 213 consent/destination cases, 55 metadata checks; all eight changed Git blobs equal PR HEAD | Run belongs to QA SHA `4f4d7380f163d3df91acc09bb3eef5cd79dadd25`; it built **Next 16.3.6**, not #840 |
| [#837 isolated QA 40591804637](https://github.com/tncommerce/commerce-agents/actions/runs/40591804637) | 163 Python/PostgreSQL cases; changed code, SQL and test blobs match PR HEAD `43b2793c754f18b47c335fef0f7348b77f22029e` | Run belongs to QA SHA `705fdd1dea84d69cc2ba9dcb71e6ca7d207d0715`; no production migration or confirmed Enhanced source |

Current PR #823 and #837 HEADs expose no required check-runs. Their isolated,
source-bound results remain valid technical evidence, but cannot be relabelled as
formal required PR checks. PR descriptions contain superseded historical SHA/CI
paragraphs; the exact refs above are the verified current state.

## New checks on the combined tree

1. `npm ci --no-audit --no-fund` completed from the unchanged #840 lockfile.
2. Actual module resolution from the storefront package confirmed **Next 16.4.3,
   Sharp 0.35.5, librsvg 2.63.2 and source-map-js 1.2.2**. Other example applications
   still resolve older Next/Sharp copies; this patch does not claim to secure them.
3. The existing prebuild gates passed, including actual source-transpiled consent,
   offer-visibility, attribution, identity, image-rights and stale-offer checks.
4. The Next static production build compiled, typechecked and generated **105
   static pages**. Existing `next/font/google` required read-only font-download
   access. The sandbox-only compilation was stopped; compilation then succeeded
   with that access and without modifying source or dependency versions.
5. Postbuild export/privacy boundaries and **55 metadata checks** passed.
6. New focused Chromium integration passed **21/21** cases:
   - four late-consent/grant/withdrawal/regrant widths;
   - two actual browser cases with `IntersectionObserver` absent: a functional
     merchant CTA remains visible and **zero unproved offer impressions** appear;
   - 15 search/navigation/variant/attribution/conversion cases from the existing QA.

The browser used Playwright **1.55.0**, Chromium **140.0.7339.16**, local static
HTML and synthetic API fixtures. **Zero merchant clickouts, zero external requests
sent and zero page errors.** The guard blocked 288 external resource attempts;
merchant images were deliberately not downloaded or visually recertified. The
separate late-consent harness also aborted its exact licensed image requests.
This is local integration evidence with Node **24.22.1**, not a claimed Render
deployment or a repeat of the full 178-page suite.

## Remaining release gates

- Explicit production and cost authorization, including actual Render build
  allowance, remains required by the owner. No approval is inferred here.
- Keep the exact selected release contents pinned. If both PRs ship together,
  verify that the final candidate contains this same application tree plus only
  separately reviewed release metadata. A changed source/dependency tree needs
  checks for that actual delta.
- Respect the active [scentai-mvp ruleset](https://github.com/tncommerce/commerce-agents/rules/25193573):
  `web`, `python (3.11)`, `python (3.12)`, `no-pypi-fallback`, `budget-postgres`,
  `private-broker-container`, and resolved review conversations. The ruleset has
  no bypass actors and does not require an up-to-date branch. A combined local
  smoke does not substitute for these check contexts on the merge candidate.
- #837's runtime migration, enhanced-feed/source eligibility and separate release
  decision remain independent. Do not add commerce changes to this security tree.
- [Gmail #802](https://github.com/tncommerce/commerce-agents/pull/802), current
  `39978a57820e7dbd68d22b803c748fe46a556554`, remains default-off and separate.
  Independent token refresh does not prove ingest/ack/finalize completion. Its
  scheduler identity, Cloud resources, cost allowance and activation require
  their own review; no OAuth or scheduler loop was started.

## Security impact qualification

The upstream [Next advisory](https://github.com/vercel/next.js/security/advisories/GHSA-2464-fhr4-w9xw)
describes possible code execution through server Image Optimization with SVG on
glibc Linux; the patch floor is Next 16.4.1 or Sharp 0.35.5. The
[Sharp advisory](https://github.com/lovell/sharp/security/advisories/GHSA-wq5f-xc86-pv6w)
identifies the fixed librsvg 2.63.2. The
[source-map-js advisory](https://github.com/advisories/GHSA-68fv-2mgg-jv7q)
sets its fixed floor at 1.2.2 for indexed-source-map denial of service.

The actual DUFYND Next configuration is `output: "export"`. Static hosting does
not expose the Next server Image Optimization endpoint; a vulnerable dependency
finding is therefore not proof of an exploitable live endpoint. The dependency
patch remains appropriate for the build environment and future runtime safety.
No exploit traffic was sent to production.

## Reproduction

Use an isolated worktree at #823 and apply only #840's three dependency files.
Before adding evidence, `git write-tree` must equal the combined tree recorded
above. Use the pinned lockfile, `NEXT_TELEMETRY_DISABLED=1` and
`DUFYND_RUNTIME_OFFER_SNAPSHOTS=disabled`. Build the storefront using its existing
prebuild/build/postbuild scripts and serve its export through
`examples/retail/storefront-web/scripts/serve-static-export.mjs` on localhost.

Run the added smoke with Playwright 1.55.0 installed separately from the lockfile:

```sh
DUFYND_PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
  node artifacts/dufynd-security-privacy-integration-20261028/run-local-smoke.mjs \
  http://127.0.0.1:3018 /tmp/dufynd-combined-browser
```

The runner refuses a non-local base URL. It writes its local result and always
closes Chromium. It is an evidence runner for the **combined candidate**, not a
production monitor or a source of live prices.
