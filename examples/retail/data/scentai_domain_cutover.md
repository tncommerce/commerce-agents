# DUFYND Custom Domain / SEO Cutover

Status: primary_domain_verified_rebrand_deploy_pending
Updated: 2026-09-19

The temporary Render URL remains functional, but the storefront must stay non-indexable until DUFYND is connected and the final public-domain smoke test passes.

## Current build-time defaults

- `NEXT_PUBLIC_SITE_URL` falls back to `https://scentai-xxya.onrender.com`
- `NEXT_PUBLIC_SITE_INDEXABLE` defaults to false unless explicitly set to `true`
- While indexability is false, pages emit noindex/nofollow metadata and `robots.txt` blocks crawling

## Brand / domain decision

DUFYND was selected as the replacement public brand after preliminary clearance. The owner purchased:
- dufynd.de via INWX on 2026-09-19
- dufynd.com via INWX on 2026-09-19

Canonical public target:
- https://dufynd.de

Protective / secondary domain:
- https://dufynd.com

Search indexing remains disabled until DNS, TLS, public branding and the production smoke test are complete.

## Cutover sequence

1. Add the custom domain in Render.
2. Configure the DNS records requested by Render.
3. Use `https://dufynd.de` as the canonical hostname. Root-domain mode is intentional; `www.dufynd.de` should redirect to it.
4. Set frontend environment variable:
   - `NEXT_PUBLIC_SITE_URL=https://dufynd.de`
5. Keep `NEXT_PUBLIC_SITE_INDEXABLE=false` during the DNS/SSL verification period.
6. Add the final frontend origin to backend `DEMO_ALLOWED_ORIGINS`.
7. Verify:
   - homepage
   - advisor API connection
   - product details
   - merchant clickout
   - analytics events
   - impressum
   - datenschutz
   - transparenz
   - `/robots.txt`
   - `/sitemap.xml`
8. After the DUFYND public smoke test passes, update the public website/advertising-space URL in Awin, CJ and other partner-network profiles.
9. Update social profiles and future campaign links to `https://dufynd.de`.
10. Only after the final-domain smoke test passes, set:
    - `NEXT_PUBLIC_SITE_INDEXABLE=true`
11. Redeploy the frontend.
12. Confirm the canonical URL, robots rules and sitemap all use the final domain.

## Important

Do not enable indexing on the temporary Render hostname before the canonical domain is ready. This reduces the chance of search engines indexing the temporary infrastructure URL and avoids a later SEO migration.


## DNS target plan

For dufynd.de on INWX:
- root / @: Render root-domain target (A record to Render load balancer if INWX does not offer ANAME/ALIAS flattening)
- www: CNAME to the current Render storefront hostname
- remove conflicting AAAA records during Render verification

For dufynd.com:
- keep registered as a defensive domain
- configure a permanent redirect to https://dufynd.de after the primary domain is verified
- do not create a second independently indexed site


## Cutover progress — 2026-09-19

Primary domain:
- dufynd.de added to the Render storefront service
- Render domain verification: verified
- TLS certificate: issued
- www.dufynd.de: verified and configured by Render to redirect to dufynd.de

INWX DNS:
- root / apex A -> 216.24.57.1
- www CNAME -> scentai-xxya.onrender.com
- INWX NS and SOA retained

Propagation note:
- Render has already verified the new records and issued TLS
- some external recursive resolvers may temporarily retain the previous INWX parking address until cached TTLs expire
- do not change DNS while propagation is converging

Next:
1. verify public HTTPS from independent resolvers/browsers after cache expiry
2. configure dufynd.com as a permanent redirect to https://dufynd.de
3. execute the public SCENTAI -> DUFYND website rebrand
4. set NEXT_PUBLIC_SITE_URL=https://dufynd.de while keeping NEXT_PUBLIC_SITE_INDEXABLE=false
5. complete smoke tests before enabling indexing


## Website rebrand state

The storefront source has been migrated to the public DUFYND brand and the default site URL is now https://dufynd.de. Production deployment/verification remains pending.

Keep NEXT_PUBLIC_SITE_INDEXABLE=false until:
- DUFYND branding is visibly live on dufynd.de
- HTTPS and www redirect are confirmed
- advisor/API calls work
- legal pages render correctly
- acquisition analytics still records events
- dufynd.com redirects permanently to dufynd.de


## Live smoke test — advisor

Verified manually on 2026-09-19 against the public DUFYND storefront:
- DUFYND wordmark and D icon visible
- guided prompt for a Louis Vuitton Imagination alternative opened successfully
- frontend created a working advisor interaction
- backend/API returned a complete recommendation response
- three alternative product cards rendered with images, prices, ratings and detail/compare actions
- no legacy SCENTAI branding was visible in the tested advisor flow

Next smoke-test targets:
1. product detail page
2. comparison page
3. legal/transparency pages
4. mobile layout
5. merchant-offer / outbound-link behavior


## Live smoke test — product quick detail

Verified manually on 2026-09-19:
- Marwa quick-detail panel opens correctly from the advisor result
- image, brand, product name, reference price and Parfumo rating render
- full-detail and compare actions are present
- merchant-offer section correctly withholds offers because no sufficiently current verified offer is available yet
- DUFYND disclosure copy is visible and no legacy SCENTAI branding appears

Trust improvement applied:
- catalogue-only market-reference prices now display as "Richtpreis" instead of a generic "ca." price so users do not confuse reference data with a live merchant offer.


## Smoke-test finding — public API origin

Observed on the public fragrance detail page on 2026-09-19:
- static fragrance detail page renders correctly
- merchant-offer request falls into the client load-error state
- direct API endpoint is healthy and returns HTTP 200 with an empty offer list
- response to Origin: https://dufynd.de does not include Access-Control-Allow-Origin

Required Render API environment update:
- add https://dufynd.de to DEMO_ALLOWED_ORIGINS
- retain the temporary Render storefront origin during the transition if it is still used for testing
- optionally add https://www.dufynd.de even though www redirects to the apex
- redeploy the API service after changing the environment variable

Polish backlog:
- add small visual note icons for top / heart / base fragrance-note sections; functionality is not blocked by this.


## Live smoke test — merchant offers CORS

Verified manually on 2026-09-19:
- public DUFYND detail page can call the Render API from https://dufynd.de
- CORS now allows dufynd.de, www.dufynd.de and the temporary Render storefront origin
- empty merchant-offer state renders correctly instead of a load error
- DUFYND correctly withholds stale/unverified offers until price and availability pass freshness checks


## Live smoke test — fragrance alternatives

Verified manually on 2026-09-19:
- Marwa detail page no longer includes unrelated cross-cluster Dubai Musk
- related section now contains only Louis Vuitton Imagination, Bujairami Hectic and Marwa Extrait
- cross-cluster broad-accord similarity is no longer sufficient for a product-detail alternative recommendation
- same-cluster or explicitly documented relationships are required


## Live smoke test — documented comparison

Verified manually on 2026-09-19:
- Marwa vs. Louis Vuitton Imagination comparison page renders successfully
- product images, community ratings, rating counts, longevity, projection, profile axes, target groups and price references are shown
- live merchant offers remain separately freshness-gated
- full fragrance-page links are present for both products

Polish applied:
- comparison accord chips translated to German
- relationship confidence labels translated to German
- remaining legacy S header marks on comparison pages replaced by the DUFYND icon


## Live smoke test — legal and trust pages

Reviewed manually on 2026-09-19:
- Impressum is reachable from the global footer and identifies TNCommerce as operator of DUFYND
- § 5 DDG reference, proprietor, postal address and contact email are rendered
- privacy notice covers Render hosting, Anthropic API, technical sessions, first-party analytics, Supabase, local wishlist/collection storage, legal bases, transfers, retention and data-subject rights
- transparency page explains recommendation independence, merchant-offer ranking, affiliate links, direct merchant entries, non-monetized products and price freshness

Compliance hardening applied:
- removed separate analytics/acquisition identifiers from browser sessionStorage
- internal analytics now relies on the running technical API session and server-side hashing
- privacy notice aligned with the implementation
- added current Anthropic commercial-API no-training-by-default disclosure
- clarified third-country transfer safeguards / DPAs

Open operational item before broad public acquisition:
- replace the Gmail contact address with a DUFYND-domain mailbox when available
- add VAT ID or Wirtschafts-ID to the Impressum only if/when one is actually issued and legally required
