# SCENTAI Launch Readiness

Status: production-hardening active
Updated: 2026-09-18

## Purpose

This checklist defines the minimum technical and operational gates before
SCENTAI is intentionally opened to broad public traffic and search indexing.

A green Render build is necessary but not sufficient. Launch readiness also
covers indexation, legal identity, API reachability, static catalog integrity,
merchant-offer freshness, privacy-minimized analytics and graceful failure
states.

## Automated launch check

From the storefront workspace:

```powershell
npm run launch:check
```

Strict launch gate:

```powershell
npm run launch:check:strict
```

The strict command exits non-zero while any launch gate remains open.

The checker validates:
- live fragrance catalog exists
- every live fragrance has source data
- live fragrance slugs are unique
- every live fragrance has a resolvable product image
- public API URL is configured with HTTPS
- canonical site URL is configured with HTTPS
- public legal identity environment variables are complete
- search-engine indexing is intentionally enabled
- merchant offers have at least one fresh customer-eligible record
- fresh affiliate-offer coverage is reported separately
- Render-hostname usage is surfaced as a warning rather than hidden

Affiliate availability is not allowed to influence recommendation quality.

## Search indexing and SEO

SCENTAI remains fail-closed for indexing:

`NEXT_PUBLIC_SITE_INDEXABLE` must equal `true` at build time before the
generated `robots.txt` allows crawling.

The storefront prebuild step generates:
- `public/robots.txt`
- `public/sitemap.xml`

The sitemap contains:
- homepage
- fragrance catalog
- comparison hub
- transparency page
- all live fragrance detail pages
- all documented explicit comparison pages

The generator uses the same slug rules and relationship types as the static
catalog. Duplicate slugs fail the build-time generator rather than publishing
an ambiguous sitemap.

Changing the canonical domain or indexability requires a new frontend build.

## Canonical metadata

Canonical URLs are explicitly defined for:
- homepage
- fragrance index
- every fragrance detail page
- comparison hub
- every documented comparison
- transparency page
- imprint
- privacy notice

Imprint and privacy pages are marked `noindex, follow` even after the main
site becomes indexable.

## Failure and recovery UX

Production fallbacks now exist for:
- unknown routes: branded 404 with catalog/advisor recovery links
- route rendering failures: retry action plus catalog fallback
- advisor/API failures: shopper-safe German message rather than local developer
  commands
- merchant-offer API outage: explicit temporary error plus retry button
- valid but empty/stale merchant-offer set: separate trust-first empty state

The distinction between an outage and "no current verified offer" is important:
SCENTAI must never imply that no seller exists merely because its API failed.

## API health

Unauthenticated health endpoint:

```text
GET /api/health
```

Expected response:

```json
{"ok": true, "service": "scentai-api"}
```

This endpoint is intended for Render health monitoring and deployment smoke
checks. It does not expose catalog, secrets, environment values or customer
data.

## Accessibility hardening

Global production styles include:
- visible keyboard focus rings
- `prefers-reduced-motion` handling
- existing labelled catalog controls
- live result-count announcements
- mobile filter state via `aria-expanded`

Future visual changes should preserve these behaviors.

## Catalog integrity

Regression coverage verifies:
- every live SCENTAI fragrance has a source-data record
- every live fragrance has a local product image
- live fragrance slugs remain unique

Build-time launch checks repeat the same safety gates outside pytest so a
deployment operator can inspect readiness without running the full suite.

## Merchant-offer trust gate

Customer-facing merchant offers remain eligible for at most 72 hours after the
last verified update.

Stale offers are hidden instead of being shown as current prices.

Launch can technically proceed without affiliate links because SCENTAI is a
recommendation product first. However, broad paid acquisition should not begin
until merchant coverage is sufficient to make the clickout experience useful.

## Analytics health

SCENTAI conversion, search-demand and research-trigger analytics remain:
- first-party
- pseudonymized by session hash
- independent of affiliate commission
- non-blocking to the shopping experience

The analytics table has RLS enabled with no public read/write policies.
Server-side writes use the Supabase secret/service-role credential.

## Required frontend environment values

Production frontend:
- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_SITE_URL`
- `NEXT_PUBLIC_SITE_INDEXABLE`
- `NEXT_PUBLIC_LEGAL_BUSINESS_NAME`
- `NEXT_PUBLIC_LEGAL_OWNER_NAME`
- `NEXT_PUBLIC_LEGAL_STREET`
- `NEXT_PUBLIC_LEGAL_POSTCODE`
- `NEXT_PUBLIC_LEGAL_CITY`
- `NEXT_PUBLIC_LEGAL_EMAIL`

Until final launch, keep:

```text
NEXT_PUBLIC_SITE_INDEXABLE=false
```

## Required API deployment checks

The API deployment must have:
- `ANTHROPIC_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY` or `SUPABASE_SERVICE_ROLE_KEY`
- storefront origin included in `DEMO_ALLOWED_ORIGINS`

Render automatically contributes its external hostname to the trusted-host
list. Custom deployment hosts outside Render must also be trusted explicitly.

## Final launch sequence

1. Deploy the candidate release and require a green Render build.
2. Check `/api/health`.
3. Smoke-test advisor, catalog, detail page, comparison and merchant clickout.
4. Run `npm run launch:check:strict` with the production environment.
5. Resolve every remaining strict gate.
6. Set the final canonical `NEXT_PUBLIC_SITE_URL`.
7. Set `NEXT_PUBLIC_SITE_INDEXABLE=true`.
8. Rebuild/redeploy the frontend so robots, sitemap and metadata change together.
9. Verify `/robots.txt` and `/sitemap.xml`.
10. Begin public distribution only after the post-deploy smoke test passes.

## Audited baseline for this hardening pass

Repository audit on 2026-09-18:
- 32 live fragrance pages
- 18 documented explicit comparison pages
- 54 generated sitemap routes including core pages
- 32/32 live fragrances have source-data rows
- 32/32 live fragrances have local product images
- no duplicate live fragrance slugs
- at least one customer-eligible merchant offer is fresh after the launch
  verification pass
- affiliate-link coverage remains commercially incomplete and is intentionally
  reported as a warning rather than allowed to affect recommendations

## Current intentional non-blockers

The following do not change recommendation ranking and are not technical
launch blockers:
- pending affiliate-program approvals
- incomplete affiliate monetization coverage
- a custom domain, provided the final canonical Render URL is intentionally
  used

They remain commercial/brand launch considerations and should be completed
before larger-scale promotion where practical.
