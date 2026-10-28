# DUFYND combined technical release — 28 October 2026

## Scope and authorization

Owner instruction following the concrete release proposal: **“leg direkt los”**.
This authorizes the described Security/Privacy/Jarvis release. The explicit
**zero additional cost** condition remains binding. It does not authorize a
plan upgrade, new model, email, social post, artificial task/clickout, price
refresh, Gmail login loop or commerce migration.

The release combines exactly:

| PR | Original head | Changed source paths |
|---|---|---:|
| #840 — dependency security | `833feefcd6e4c525ef83fcd0a3a3f9f9b72629f3` | 3 |
| #823 — visibility/consent measurement | `a9a8220d503d7db2bacfe1f4319188ca813878fa` | 8 |
| #841 — private observer/planner truth | `edce91d35aaa6bd4ebdf13124d99ecc784801743` | 24 |

Base: `36cc84c34791284e4245ab4504ae020434dca89e`.
All 35 paths are disjoint; each staged source blob matches its original PR
exactly. The source-only union tree is
`048d693436406c08bb946de110dff6b3ff15af55`.
Release/rollback documentation is additional evidence, not a code change to the
three reviewed proposals. Their Git ancestry is retained.

## Validation without repeated QA

The new release SHA needs one genuine integrated run of the six existing
required checks: `web`, `python (3.11)`, `python (3.12)`,
`no-pypi-fallback`, `budget-postgres`, `private-broker-container`.
No ruleset, required context or review gate is removed or bypassed.

The `release/*` branch name keeps the existing optional visual/RC1 jobs out of
this run. The already successful 178-page QA, three original remote CI/QA runs,
96 focused Python checks, 29 native PostgreSQL checks, combined website build,
21 Chromium cases and 55 metadata checks remain attached to their precise
source evidence. The new run tests their first complete integration, rather
than rerunning an unchanged old candidate.

## Cost and deployment controls

GitHub repository visibility was verified as public. All six required jobs use
standard `ubuntu-latest` runners. Existing cache use was
**2,959,249,102 bytes / 28 entries** (the GitHub aggregator can lag by five
minutes), safely below the included 10 GiB; the comparable #840 web job saved
about 0.48 GB of Next/npm caches. No cache limit, billing setting, paid provider
or artifact-heavy optional job is enabled.

Official sources:
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching

Both Render services remain on the production base, with auto-deploy on commit
and PR previews disabled. Existing service plans and limits must remain unchanged.
At preparation time, the connected API exposed no current remaining pipeline
minutes or live spend cap. The available browser surfaces had no authenticated
Render session. Historical purchased minutes/$5-cap evidence is not asserted to
be current. **Do not trigger a new Render build unless zero incremental cost can
be established.**

If merging the verified candidate separately from deployment, use the normal
protected PR merge with the exact expected head and the commit markers
`[skip ci] [skip render]`. This prevents duplicate push CI, an uncontrolled
intermediate deploy and push-triggered worker side effects. Render confirms that
`[skip render]` suppresses automatic deployment:
https://render.com/docs/deploys

Once the cost condition is established, deploy the single resulting production
SHA once per existing service; do not create a replacement service. Confirm
actual `live` deployment IDs/SHAs and public behavior afterwards. A trigger
receipt is not deployment success.

## Database change and rollback boundary

Only the two #841 function migrations are in scope. #837 commerce and #802 Gmail
credential recovery remain separate. Existing data, RLS policies, grants to
public roles, credentials and cron definitions are not opened or reset.

Use the exact live-definition fingerprints and ACL guards in the separate SQL
release packet. The three old function definitions are preserved for rollback.
Re-read the compact catalog fingerprints immediately before applying a migration;
abort on unexpected drift. Apply production DDL through the supported Supabase
migration interface, verify exact resulting definitions/ACLs, read the diagnostic
classifier, and observe the existing natural cron update.

Rollback functions separately from the application. Preserve real new captures,
the previous monitoring reconciliation and business evidence. For an API-only
regression, prefer API-only rollback to the retained base deployment, preserving
the storefront dependency/consent fix. A complete storefront rollback would
restore the known previous defects.

## Operational acceptance

The existing default-branch private-observer dispatcher is active, configured
with two staggered schedules that together request a read every five minutes.
The most recent read inspected during preparation was run `40656498406`,
production SHA `36cc84c3…`, failed at the existing Gmail boundary. This is a
scheduler attempt, not successful private processing.

After the release, inspect a real new production-SHA run:
- Render-only recovery may refresh Render with independently verified evidence.
- Gmail failure must remain visible; no Gmail ack or activation may be invented.
- A complete chain requires the existing finalization and acknowledgement proof.
- The planner should report technical remediation while technical evidence is
  incomplete, preserving real active/ready work and actual owner gates.
- Successful cron/CI/read activity is never counted as a sale or completed
  business action.

Current/final CI IDs, merge/deploy results and live database verification belong
in the release PR and the existing Supabase master-status handoff. This file is
the preparation record and does not claim those later actions have occurred.
