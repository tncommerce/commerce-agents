# DUFYND offer fallback audit · 25 September 2026

The catalog currently has 32 fragrance pages. `merchant_offers.json` contains four entries for two fragrances. On 25 September, only the two Naxos entries pass the 72-hour freshness gate; both Bois Impérial entries are stale. The frontend correctly omits stale price and stock claims.

## Current manufacturer fallback coverage

DUFYND now has a curated, product-specific manufacturer fallback for **all 32 of 32** catalog fragrances. The fallback is shown only when no sufficiently fresh merchant offer is available or the merchant-offer request fails.

The manufacturer fallback is informational only:

- it is not presented as a price-verified merchant offer;
- it is not presented as an affiliate link;
- DUFYND does not copy live price or stock from the manufacturer page;
- visitors are told to verify current price and availability on the destination site;
- existing fresh merchant offers remain first-class and are never suppressed by the fallback.

The current fallback map includes the following exact catalog products:

- Louis Vuitton Imagination 100 ml
- Essential Parfums Bois Impérial 100 ml
- Creed Aventus 100 ml
- Creed Absolu Aventus 100 ml
- Dior Homme Intense 100 ml
- Dior Sauvage Eau de Parfum 100 ml
- Chanel Bleu de Chanel Eau de Parfum 100 ml
- Prada L'Homme Eau de Toilette 100 ml
- Parfums de Marly Layton 125 ml
- Parfums de Marly Althaïr 125 ml
- Montblanc Explorer 100 ml
- Valentino Uomo Born in Roma Intense 100 ml
- Xerjoff Naxos 100 ml
- Giorgio Armani Stronger With You Intensely 100 ml
- Afnan Turathi Blue 90 ml
- Afnan Supremacy Collector's Edition 100 ml
- Sospiro Vibrato 100 ml
- Al Haramain Détour Noir 100 ml
- Clive Christian Jump Up and Kiss Me Hedonistic 50 ml
- Maison Asrar Vanguard 100 ml
- Maison Asrar Regent 100 ml
- Al Wataniah Kayaan Classic 100 ml
- Armaf Club de Nuit Intense Man Eau de Parfum 200 ml
- Arabiyat Prestige Marwa Eau de Parfum 100 ml
- Arabiyat Prestige Marwa Extrait 60 ml
- Rayhaan Italia Eau de Parfum 100 ml
- Bvlgari Le Gemme Tygar Eau de Parfum 125 ml
- French Avenue Liquid Brun Eau de Parfum 100 ml
- Orientica Royal Bleu Eau de Parfum 80 ml
- Al Ambra Dubai Musk Extrait de Parfum 50 ml
- Bujairami Hectic 100 ml
- Nusuk Ateeq 100 ml

Product identity was checked against manufacturer-controlled or official brand-operator product pages before adding each URL. Concentration and bottle size were also checked where the manufacturer page exposes them. When a manufacturer page does not expose a fixed size in its page content, DUFYND treats the destination only as a product-information fallback and does not claim that the catalog size is preselected.

## Coverage completed

The last two gaps were resolved on 25 September 2026 without using retailer pages as substitutes:

- **Bujairami Hectic 100 ml** now points to Bujairami's own 100 ml Hectic product page.
- **Nusuk Ateeq 100 ml** now points to the official Riiffs/Nusuk product page. Riiffs' own site exposes Nusuk as a brand and identifies the product as NUSUK Ateeq 100 ml.

These remain informational product-page fallbacks. DUFYND does not inherit live price, stock or affiliate status from either destination.

## Safety and regression gates

The fallback map is guarded by `tests/test_dufynd_official_product_pages.py`. The test verifies that:

- every linked product ID exists in the DUFYND catalog;
- each fallback URL uses HTTPS and a product-specific path;
- the hostname matches the product's manufacturer;
- no catalog fragrance remains unintentionally uncovered;
- the curated coverage stays at 32 of 32 unless the catalog deliberately changes.

This is structural QA, not a live destination check. Manufacturer pages can move or change after verification, so live-link health should still be checked periodically.

Do not refresh stale merchant-offer timestamps merely to make old prices visible. Manufacturer fallbacks do not substitute for current price comparison, affiliate approval, browser screenshot QA or visual product-fidelity review.
