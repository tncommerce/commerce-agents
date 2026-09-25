# DUFYND offer fallback audit · 25 September 2026

The catalog currently has 32 fragrance pages. `merchant_offers.json` contains four entries for two fragrances. On 25 September, only the two Naxos entries pass the 72-hour freshness gate; both Bois Impérial entries are stale. The frontend correctly omits stale price and stock claims, but visitors otherwise reach an empty offer panel.

Sixteen catalog products now have a curated official product page in `officialProductPages.ts`: Louis Vuitton Imagination, Essential Parfums Bois Impérial, Creed Aventus, Creed Absolu Aventus, Dior Homme Intense, Dior Sauvage Eau de Parfum, Bleu de Chanel Eau de Parfum, Prada L'Homme Eau de Toilette, Parfums de Marly Layton and Althaïr, Montblanc Explorer, Valentino Uomo Born in Roma Intense, Xerjoff Naxos, Giorgio Armani Stronger With You Intensely, Afnan Turathi Blue and Sospiro Vibrato. Product identity, concentration and listed bottle size were checked against their manufacturer pages on 25 September. The Armani URL selects 100 ml; Xerjoff, Afnan and Sospiro list 100 ml, 90 ml and 100 ml respectively. Some manufacturer pages let visitors choose from several sizes; DUFYND does not assume which size the destination selects. The original manufacturer URLs are recorded in that file.

When offers are absent or the offer API fails, the panel shows a separate direct manufacturer link if one is curated. It does not represent this link as an eligible, price-verified merchant offer or affiliate link. Price and availability must be checked on the destination site. Existing fresh offers remain first-class; no fallback suppresses them.

Before expanding coverage, verify the exact product and size on the manufacturer's website and add only its matching URL. Do not refresh merchant offer timestamps merely to make stale prices visible. Direct manufacturer links do not substitute for browser screenshot QA or current price comparison.

Bvlgari Le Gemme Tygar Eau de Parfum was not added in this pass: the official collection lists a 125 ml variant, while the accessible product page did not confirm that the URL selects that size. The Extrait de Parfum is a separate variant and must not be linked to the Eau de Parfum catalog entry.

The official Armaf UK site has an exact 200 ml Eau de Parfum page for Club de Nuit Intense Man, but it was held back as a German-facing fallback: the UK page showed GBP and sold out status at the time of verification. No availability claim or UK buying route was added for the German catalog page.

The fallback map now has a regression check (`tests/test_dufynd_official_product_pages.py`). It ensures every linked product ID exists in the catalog, each HTTPS URL has a product-specific path, and its host belongs to that product's manufacturer. This is structural QA, not a live destination check or visual approval. The unresolved screenshot QA and unverified Bois Impérial front bottle remain open.
