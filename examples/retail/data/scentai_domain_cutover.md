# DUFYND Custom Domain / SEO Cutover

Status: domains_purchased_pending_dns_cutover
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
