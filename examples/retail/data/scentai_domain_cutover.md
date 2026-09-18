# SCENTAI Custom Domain / SEO Cutover

Status: prepared
Updated: 2026-09-18

The temporary Render URL remains functional, but SCENTAI should stay non-indexable until the final public domain is connected.

## Current build-time defaults

- `NEXT_PUBLIC_SITE_URL` falls back to `https://scentai-xxya.onrender.com`
- `NEXT_PUBLIC_SITE_INDEXABLE` defaults to false unless explicitly set to `true`
- While indexability is false, pages emit noindex/nofollow metadata and `robots.txt` blocks crawling

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
