# SCENTAI Custom Domain / SEO Cutover

Status: prepared_brand_clearance_required
Updated: 2026-09-19

The temporary Render URL remains functional, but SCENTAI should stay non-indexable until the final public domain is connected.

## Current build-time defaults

- `NEXT_PUBLIC_SITE_URL` falls back to `https://scentai-xxya.onrender.com`
- `NEXT_PUBLIC_SITE_INDEXABLE` defaults to false unless explicitly set to `true`
- While indexability is false, pages emit noindex/nofollow metadata and `robots.txt` blocks crawling

## Brand-clearance gate

Before purchasing or connecting the final public domain, complete a brand-clearance decision for the SCENTAI name.

Reason:
- active third-party fragrance services currently use the ScentAI/ScentAi name in a closely related fragrance-discovery category
- a separate company named ScentAI Inc. also exists in the smell/AI technology space
- the current domain cutover therefore remains technically prepared but commercially paused pending the owner's naming decision

Do not:
- purchase a long-term domain commitment
- enable public search indexing
- migrate partner-network public URLs
- start paid acquisition

until this brand-clearance gate is explicitly resolved.

The temporary Render hostname stays non-indexable during this decision.

## When the final domain is purchased

1. Add the custom domain in Render.
2. Configure the DNS records requested by Render.
3. Choose one canonical hostname, for example `https://scentai.de` or `https://www.scentai.de`.
4. Set frontend environment variable:
   - `NEXT_PUBLIC_SITE_URL=https://<final-domain>`
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
8. Update the public website/advertising-space URL in Awin, CJ and other partner-network profiles.
9. Update social profiles and future campaign links to the canonical domain.
10. Only after the final-domain smoke test passes, set:
    - `NEXT_PUBLIC_SITE_INDEXABLE=true`
11. Redeploy the frontend.
12. Confirm the canonical URL, robots rules and sitemap all use the final domain.

## Important

Do not enable indexing on the temporary Render hostname before the canonical domain is ready. This reduces the chance of search engines indexing the temporary infrastructure URL and avoids a later SEO migration.
