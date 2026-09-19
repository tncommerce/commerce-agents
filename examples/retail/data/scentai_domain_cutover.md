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
