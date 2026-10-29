# DUFYND Search Console delta — 29 October 2026

## Evidence and scope

Read the existing authenticated `sc-domain:dufynd.de` property in the official
[Search Console](https://search.google.com/search-console?resource_id=sc-domain%3Adufynd.de).
No account recovery, new authorization, indexing submission, merchant clickout,
or website JavaScript was performed. The Google/Gmail recovery pause remains in
effect. Website checks below used plain HTTP on 29 October at 09:03 UTC against
the existing storefront release `063f4f2ca0a6403137c6f5e94a71f0ec593e6a98`.

Windsor's connected Search Console source returned `status: done` but explicitly
said its values were not real: reads were paused because four connected accounts
exceeded the one-account Free plan allowance. Those placeholder values were
discarded. No account was disconnected and no plan was upgraded.

## Actual Google reports

| Report | Observed result | Reporting limit |
| --- | --- | --- |
| Page indexing | 43 indexed; 24 not indexed | Last updated 23 October 2026 |
| Alternative page with proper canonical | 1 URL | First detected 20 October; last crawl 14 October |
| Excluded by noindex | 4 URLs | Last crawl 20 September |
| Discovered, currently not indexed | 19 URLs | No crawl date recorded in these examples |
| Crawled, currently not indexed | 0 URLs | Reported status, not a claim about future indexing |
| Sitemap | Successful; 62 discovered pages, 0 videos | Submitted 19 September; last read 28 October |
| Search performance, Web, selected last three months | 1 click; 213 impressions; 0.5% CTR; average position 23.1 | Chart's visible data span: 18 September–27 October; UI last updated four hours before inspection |
| Core Web Vitals | No data for mobile or desktop | No field-performance score can be inferred |

The single reported click belongs to
`/vergleich/arabiyat-prestige-marwa-vs-louis-vuitton-imagination` (17 impressions
for that page in the selected period). These are Google search metrics, not
merchant clicks, sales, affiliate attribution, or revenue.

## Canonical and noindex findings

The exact alternative URL is
`https://dufynd.de/duft/parfums-de-marly-delina?src=unknown`.
Its live HTTP response is 200 and declares the clean canonical
`https://dufynd.de/duft/parfums-de-marly-delina`. The clean URL is also 200,
self-canonical, `index, follow`, and present in the sitemap. The query variant
is absent from the sitemap. This matches the intended canonical behavior;
there is no demonstrated canonical defect to repair.

All four noindex URLs are intentional in the current source and live HTML:
`/merkliste`, `/sammlung`, `/impressum`, `/datenschutz`. They return 200 with
`noindex, follow` and are absent from the sitemap. Do not remove their noindex
directives merely to make the indexing report green.

Google documents both proper canonical alternatives and intentional noindex
exclusions in its
[Page indexing report guidance](https://support.google.com/webmasters/answer/7440203).

## The 19 discovered URLs

Every URL below was checked once in a bounded HTTP batch. All returned 200 with
one matching self-canonical, `index, follow`, no `X-Robots-Tag` exclusion, and a
matching sitemap entry. All embedded JSON-LD parsed successfully. The six
fragrance pages included `Product`; comparison pages included `BreadcrumbList`.
This checks technical availability and syntax, not rich-result eligibility or
an assurance that Google will index the pages.

- `/duft/bujairami-hectic`
- `/duft/bvlgari-le-gemme-tygar`
- `/duft/creed-absolu-aventus`
- `/duft/lancome-la-vie-est-belle`
- `/duft/nusuk-ateeq`
- `/duft/xerjoff-naxos`
- `/vergleich/afnan-perfumes-supremacy-collectors-edition-vs-creed-absolu-aventus`
- `/vergleich/afnan-perfumes-turathi-blue-vs-bvlgari-le-gemme-tygar`
- `/vergleich/afnan-perfumes-turathi-blue-vs-sospiro-vibrato`
- `/vergleich/al-haramain-detour-noir-vs-parfums-de-marly-layton`
- `/vergleich/al-wataniah-kayaan-classic-vs-dior-dior-homme-intense`
- `/vergleich/arabiyat-prestige-marwa-extrait-vs-louis-vuitton-imagination`
- `/vergleich/bujairami-hectic-vs-louis-vuitton-imagination`
- `/vergleich/bvlgari-le-gemme-tygar-vs-maison-asrar-regent`
- `/vergleich/bvlgari-le-gemme-tygar-vs-sospiro-vibrato`
- `/vergleich/creed-absolu-aventus-vs-maison-asrar-vanguard`
- `/vergleich/creed-aventus-vs-montblanc-explorer`
- `/vergleich/nusuk-ateeq-vs-xerjoff-naxos`
- `/vergleich/rayhaan-italia-vs-xerjoff-naxos`

The live sitemap contains 62 URLs. `robots.txt` allows crawling and references
that sitemap. This report identifies the pending URLs and rules out the tested
blocking mechanisms; it does not establish Google's reason for delaying their
crawl. Reassess the same set when Google's report advances beyond 23 October.
No SEO source or accepted design change was warranted by this evidence.
