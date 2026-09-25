# DUFYND offer fallback audit · 25 September 2026

The catalog currently has 32 fragrance pages. `merchant_offers.json` contains four entries for two fragrances. On 25 September, only the two Naxos entries pass the 72-hour freshness gate; both Bois Impérial entries are stale. The frontend correctly omits stale price and stock claims, but visitors otherwise reach an empty offer panel.

Twelve catalog products now have a curated official product page in `officialProductPages.ts`: Louis Vuitton Imagination, Essential Parfums Bois Impérial, Creed Aventus, Creed Absolu Aventus, Dior Homme Intense, Dior Sauvage Eau de Parfum, Bleu de Chanel Eau de Parfum, Prada L'Homme Eau de Toilette, Parfums de Marly Layton and Althaïr, Montblanc Explorer and Valentino Uomo Born in Roma Intense. Product identity, concentration and listed bottle size were checked against their manufacturer pages on 25 September. Some manufacturer pages let visitors choose from several sizes; DUFYND does not assume which size the destination selects. The original manufacturer URLs are recorded in that file.

When offers are absent or the offer API fails, the panel shows a separate direct manufacturer link if one is curated. It does not represent this link as an eligible, price-verified merchant offer or affiliate link. Price and availability must be checked on the destination site. Existing fresh offers remain first-class; no fallback suppresses them.

Before expanding coverage, verify the exact product and size on the manufacturer's website and add only its matching URL. Do not refresh merchant offer timestamps merely to make stale prices visible. Direct manufacturer links do not substitute for browser screenshot QA or current price comparison.
