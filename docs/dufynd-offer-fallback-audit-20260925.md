# DUFYND offer fallback audit · 25 September 2026

The catalog currently has 32 fragrance pages. `merchant_offers.json` contains four entries for two fragrances. On 25 September, only the two Naxos entries pass the 72-hour freshness gate; both Bois Impérial entries are stale. The frontend correctly omits stale price and stock claims, but visitors otherwise reach an empty offer panel.

Nineteen catalog products now have a curated official product page in `officialProductPages.ts`: Louis Vuitton Imagination, Essential Parfums Bois Impérial, Creed Aventus, Creed Absolu Aventus, Dior Homme Intense, Dior Sauvage Eau de Parfum, Bleu de Chanel Eau de Parfum, Prada L'Homme Eau de Toilette, Parfums de Marly Layton and Althaïr, Montblanc Explorer, Valentino Uomo Born in Roma Intense, Xerjoff Naxos, Giorgio Armani Stronger With You Intensely, Afnan Turathi Blue and Supremacy Collector's Edition, Sospiro Vibrato, Al Haramain Détour Noir and Clive Christian Jump Up and Kiss Me Hedonistic. Product identity, concentration and listed bottle size were checked against their manufacturer pages on 25 September. The Armani URL selects 100 ml; Xerjoff, Turathi Blue, Supremacy Collector's Edition and Sospiro list 100 ml, 90 ml, 100 ml and 100 ml respectively. Al Haramain's EU page states 100 ml Eau de Parfum, and Clive Christian's official collection lists Hedonistic at 50 ml. Some manufacturer pages let visitors choose from several sizes; DUFYND does not assume which size the destination selects. The original manufacturer URLs are recorded in that file.

When offers are absent or the offer API fails, the panel shows a separate direct manufacturer link if one is curated. It does not represent this link as an eligible, price-verified merchant offer or affiliate link. Price and availability must be checked on the destination site. Existing fresh offers remain first-class; no fallback suppresses them.

Before expanding coverage, verify the exact product and size on the manufacturer's website and add only its matching URL. Do not refresh merchant offer timestamps merely to make stale prices visible. Direct manufacturer links do not substitute for browser screenshot QA or current price comparison.

Bvlgari Le Gemme Tygar Eau de Parfum was not added in this pass: the official collection lists a 125 ml variant, while the accessible product page did not confirm that the URL selects that size. The Extrait de Parfum is a separate variant and must not be linked to the Eau de Parfum catalog entry.

The official Armaf UK site has an exact 200 ml Eau de Parfum page for Club de Nuit Intense Man, but it was held back as a German-facing fallback: the UK page showed GBP and sold out status at the time of verification. No availability claim or UK buying route was added for the German catalog page.

The Al Haramain EU page showed sold-out status at verification. Its link serves product information only; the fallback does not claim stock or show a merchant offer.

The fallback map now has a regression check (`tests/test_dufynd_official_product_pages.py`). It ensures every linked product ID exists in the catalog, each HTTPS URL has a product-specific path, and its host belongs to that product's manufacturer. This is structural QA, not a live destination check or visual approval. The unresolved screenshot QA and unverified Bois Impérial front bottle remain open.


## Additional manufacturer fallbacks verified 2026-09-25

Four more catalog products now have a product-specific manufacturer fallback:

- Maison Asrar Vanguard — official Maison Asrar product page.
- Maison Asrar Regent — official Maison Asrar product page.
- Al Wataniah Kayaan Classic — official Al Wataniah product page.
- Armaf Club de Nuit Intense Man Eau de Parfum 200 ml — official Armaf product page; the manufacturer page explicitly exposes the Eau de Parfum in the 6.8 oz size (approximately 200 ml).

This first pass raised the curated manufacturer fallback coverage from 19/32 to 23/32 catalog fragrances. No live price or stock value is imported from these pages; DUFYND uses them only as neutral manufacturer fallbacks when no sufficiently fresh merchant offer is available.


## Coverage extension to 30/32

A second verification pass added exact manufacturer pages for:

- Arabiyat Prestige Marwa EDP 100 ml.
- Arabiyat Prestige Marwa Extrait 60 ml.
- Rayhaan Italia EDP 100 ml.
- Bvlgari Le Gemme Tygar EDP 125 ml.
- French Avenue Liquid Brun EDP 100 ml.
- Orientica Royal Bleu EDP 80 ml.
- Al Ambra Dubai Musk Extrait de Parfum 50 ml.

The curated manufacturer fallback coverage is now **30 of 32** catalog fragrances.

The two intentionally unresolved products are **Bujairami Hectic 100 ml** and **Nusuk Ateeq 100 ml**. Search results currently surfaced retailers or secondary sources rather than a manufacturer-controlled product page that satisfies the same evidence standard, so DUFYND leaves them without a manufacturer fallback rather than guessing.
