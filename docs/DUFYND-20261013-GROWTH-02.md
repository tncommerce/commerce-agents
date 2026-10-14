# DUFYND-20261013-GROWTH-02

Development-only extraction from Draft #774 at a21ebf53a812c32d1817a5ca9a8e5e88d8797f9e.
Base: unchanged production d3e948ebeb22c944ad143b20e644d0c0c5f4b186.
Run claimed once in ops.DUFYND-20261013-GROWTH-02 on 2026-10-13.
Funnel-01 is complete and was not repeated. No production or Nightshift write.

## Narrow discovery change

Extracted brand identity/grouping, A–Z directory and scoped brand routes from #774.
Only the existing LIVE_FRAGRANCES boundary supplies data. Added desktop/mobile links
from /duft. The mobile navigation wraps. Brand pages link directly to exact existing
product paths, with concentration and size visible before opening the product.

Adaptations for independent review: brand product lists contain text only, so they
cannot expose a new photo, editorial bottle, price, stock or merchant CTA. No catalog,
source product, review, qualified renderer, image registry, offer or release gate was
copied. All new directory routes remain noindex; follow respects the global indexing
gate. No new sitemap route or indexing authorization. Existing product canonical URLs
and metadata are unchanged. The #774 metadata fix only affects its unreleased qualified
renderer and was intentionally not copied into the unrelated production route.

| Evidence | Before (production base) | Isolated development |
| --- | --- | --- |
| Brand directory | absent | /marken |
| Brand routes | absent | 29, noindex, stable canonical URLs |
| Exact public product identities | 37 | same 37, each listed once |
| Review/source hold excluded by live boundary | 1 | same 1 excluded |
| /duft mobile brand entry | absent | Marken A–Z, wrapping navigation |
| New products/images/offers | 0 | 0 |
| Existing sitemap route count | 62 | 62 |

Validation performed locally: Next.js 16.3.6 production build and TypeScript check;
offline executable route/metadata tests for both global indexing states, identity
aliases, every public brand, existing blocked identities and unknown-brand notFound;
static HTML inspection of all 29 brand routes and all 37 exact product links.
The test runs in the existing prebuild hook. Browser QA is wired into the existing
visual CI job for 390px and 1440px: all brand routes, canonical/noindex, search, overflow,
text-only product lists and Rabanne navigation. It permits localhost only and blocks
external traffic and API writes. Local Chromium was unavailable; do not label the
local build/HTML checks as a browser or live production PASS. Exact CI result is recorded
in the associated PR and central run checkpoint after completion.

## Three source-qualified, blocked import packets

File: `dufynd-growth-02-import-hold.json`. Reuses the original #774 source packet and
records its full source-file SHA256 and commit. Direct official pages were read again
on 2026-10-13; identity, concentration, selected size and dedicated note pyramid agree.
Existing content originals and candidate registry remain unchanged. Merchant research
is reused with its original 2026-10-12 date, not represented as a fresh price/stock check.

| Candidate | Proposed exact product ID (unregistered) | Official reference |
| --- | --- | --- |
| BDK-GRIS-CHARNEL-EDP | SC-BDK-GRIS-CHARNEL-EDP-100 | gris-charnel, variant 45617631232284; EDP 100 ml |
| MONTALE-ARABIANS-TONKA-EDP | SC-MONTALE-ARABIANS-TONKA-EDP-100 | 282-arabians-tonka; EDP 100 ml |
| PDM-VALAYA-EDP | SC-PDM-VALAYA-EDP-75 | valaya; EDP 75 ml |

Official source URLs and manufacturer note pyramids are retained in each packet:
- https://bdkparfums.com/en/products/gris-charnel?variant=45617631232284
- https://www.montaleparfums.com/en/oriental/282-arabians-tonka.html
- https://parfums-de-marly.com/de/products/valaya

Both production and #774 have these candidate IDs but no exact registered/staged SKU.
Existing SC-PDM-VALAYA-EXCLUSIF-EDP-75 is distinct; it is not reused. No official GTIN
is established by the inspected evidence: canonical_gtin=null, observations=[].
No community data, prices, availability, affiliate URL or image rights were invented.

**Newly staging-ready: 0; fully mapped blocked import packets: 3.**
The existing validate_wave function returns exactly
candidate_1:merchant_1:invalid_affiliate_state,
candidate_2:merchant_1:invalid_affiliate_state,
candidate_3:merchant_1:invalid_affiliate_state.
The verified manufacturer facts do not establish affiliate approval. UNKNOWN cannot
honestly be replaced by application_pending or not_applicable_direct_merchant simply
to satisfy the legacy intake enum. Accordingly no intake config is enabled and no
staging/catalog/database row is written. Separate image rights, review design/QA,
current merchant destination and owner release gates remain closed.

## Protected state and next step

No merge, deployment, main/scentai-mvp change, productive migration, social publication,
visitor event or merchant clickout. No changes to PR #779, its approved commit, manifest,
mission, two tasks, owner decision, Cron 11 or 22:00–22:45 Europe/Berlin window.
This is not the 21:59 Nightshift activation task; its existing private guarded activation
action remains separately required and is not scheduled by this work.

Next scoped DUFYND task: review this isolated brand-discovery PR after exact CI/browser
results; decide its release independently of the #774 catalog wave. The import packets
remain available for a later facts-only staging contract without invented affiliate state.
