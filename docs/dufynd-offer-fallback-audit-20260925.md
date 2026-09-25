# DUFYND offer fallback audit · 25 September 2026

The catalog currently has 32 fragrance pages. `merchant_offers.json` contains four entries for two fragrances. On 25 September, only the two Naxos entries pass the 72-hour freshness gate; both Bois Impérial entries are stale. The frontend correctly omits stale price and stock claims.

## Current manufacturer fallback coverage

DUFYND now has a curated, product-specific manufacturer fallback for **30 of 32** catalog fragrances. The fallback is shown only when no sufficiently fresh merchant offer is available or the merchant-offer request fails.

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

Product identity, concentration and listed bottle size were checked against manufacturer-controlled product pages before adding each URL. Some manufacturer pages expose more than one selectable size; DUFYND does not claim that a destination has preselected the catalog size unless that is explicitly encoded in the URL.

## Intentionally unresolved

Two products remain without a manufacturer fallback:

- **Bujairami Hectic 100 ml**
- **Nusuk Ateeq 100 ml**

Current search evidence surfaced retailers or secondary sources rather than a manufacturer-controlled product page that meets the same verification standard. DUFYND leaves these unresolved instead of guessing.

## Safety and regression gates

The fallback map is guarded by `tests/test_dufynd_official_product_pages.py`. The test verifies that:

- every linked product ID exists in the DUFYND catalog;
- each fallback URL uses HTTPS and a product-specific path;
- the hostname matches the product's manufacturer;
- exactly the two intentionally unresolved catalog IDs remain uncovered;
- the curated coverage stays at 30 of 32 unless the unresolved set is deliberately changed.

This is structural QA, not a live destination check. Manufacturer pages can move or change after verification, so live-link health should still be checked periodically.

Do not refresh stale merchant-offer timestamps merely to make old prices visible. Manufacturer fallbacks do not substitute for current price comparison, affiliate approval, browser screenshot QA or visual product-fidelity review.
