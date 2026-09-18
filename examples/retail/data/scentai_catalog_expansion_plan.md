# SCENTAI Catalog Expansion Plan

Status: active
Target: 150 live SCENTAI fragrances
Current live SCENTAI catalog: 32 fragrances
Required additions: 118

## Why expansion is the next priority

The current SCENTAI catalog is heavily skewed toward men's and male-leaning unisex fragrances. The next expansion must improve mainstream demand coverage, women's fragrance coverage, niche discovery, and Arabic/value alternatives while keeping the catalog curated.

The live catalog should not be bulk-filled with low-quality or invented data. New products are promoted to live only after core facts are verified.

## Non-negotiable quality gates

- Never invent EAN/GTIN, merchant IDs, prices, ratings, review counts, notes, or affiliate URLs.
- Keep one canonical SCENTAI product per fragrance/size/concentration identity.
- Merchant offers attach underneath the canonical product.
- Affiliate commission must never affect recommendation ranking or merchant ranking.
- Product relationships such as clone/inspired/alternative must be evidence-backed before going live.
- Prefer verified merchant-feed images once partner feeds are available.
- Do not use a generated product image if it materially misrepresents the real bottle.
- Prices must include a checked-at timestamp and source semantics.
- Products may enter the candidate backlog before all commerce fields are available.

## Target portfolio at 150

The final 150 should cover four commercial/recommendation needs:

1. Mainstream men's designer fragrances
2. Mainstream women's designer fragrances
3. Niche and premium discovery
4. Arabic/value/dupe ecosystem

Audience balance is a priority because the current 32-product catalog contains no women-only fragrance entries.

## Wave 1 — 40 high-priority additions

### Men's designer / mainstream — 14

1. Yves Saint Laurent MYSLF Eau de Parfum
2. Jean Paul Gaultier Le Male Le Parfum
3. Jean Paul Gaultier Le Male Elixir
4. Jean Paul Gaultier Le Beau Le Parfum
5. Jean Paul Gaultier Le Beau Paradise Garden
6. Versace Eros Eau de Parfum
7. Hugo Boss BOSS Bottled Eau de Toilette
8. Yves Saint Laurent Y Eau de Parfum
9. Prada Paradigme Eau de Parfum
10. Prada L'Homme Intense Eau de Parfum
11. Giorgio Armani Acqua di Giò Eau de Toilette
12. Viktor & Rolf Spicebomb Extreme Eau de Parfum
13. Gisada Ambassador Men Eau de Parfum
14. Hermès Terre d'Hermès Eau Givrée

### Women's designer / mainstream — 12

15. Yves Saint Laurent Libre Eau de Parfum
16. Prada Paradoxe Eau de Parfum
17. Burberry Goddess Eau de Parfum
18. Carolina Herrera Good Girl Eau de Parfum
19. Lancôme La Vie Est Belle Eau de Parfum
20. Giorgio Armani Sì Eau de Parfum
21. Narciso Rodriguez For Her Pure Musc Eau de Parfum
22. Zadig & Voltaire This Is Her! Eau de Parfum
23. Gucci Flora Gorgeous Gardenia Eau de Parfum
24. Jean Paul Gaultier La Belle Eau de Parfum
25. Chloé Chloé Eau de Parfum
26. Yves Saint Laurent Black Opium Eau de Parfum

### Niche / premium — 8

27. Parfums de Marly Delina Eau de Parfum
28. Parfums de Marly Valaya Eau de Parfum
29. Parfums de Marly Herod Eau de Parfum
30. BDK Parfums Gris Charnel Eau de Parfum
31. Initio Parfums Privés Side Effect Eau de Parfum
32. Nishane Ani Extrait de Parfum
33. Montale Arabians Tonka Eau de Parfum
34. Tom Ford Ombré Leather Eau de Parfum

### Arabic / value / dupe ecosystem — 6

35. Lattafa Khamrah Eau de Parfum
36. Lattafa Yara Eau de Parfum
37. Lattafa Eclaire Eau de Parfum
38. Lattafa Pride Art of Arabia I Eau de Parfum
39. Afnan 9PM Eau de Parfum
40. Rasasi Hawas for Him Eau de Parfum

After Wave 1: 72 live fragrances if every candidate passes verification.

## Wave 2 — +40

Build from approved affiliate product feeds and verified high-demand gaps.

Priority families:
- Jean Paul Gaultier
- Dior
- Chanel
- Prada
- Yves Saint Laurent
- Armani
- Valentino
- Rabanne
- Tom Ford
- Parfums de Marly
- Xerjoff
- Mancera
- Montale
- Initio
- Lattafa
- Afnan
- Armaf
- French Avenue
- Paris Corner
- Khadlaj

Wave 2 should especially add:
- more women's alternatives and affordable options
- summer/fresh coverage
- gourmand/vanilla coverage
- office/everyday coverage
- date/evening coverage
- additional high-demand original-vs-alternative clusters

After Wave 2: 112 fragrances.

## Wave 3 — +38

Use real query/analytics data plus merchant-feed coverage to fill the remaining gaps.

Selection inputs:
- customer searches that return no exact product
- products repeatedly requested by name
- categories with weak shortlist diversity
- high-coverage products available from multiple approved merchants
- seasonal demand
- emerging Arabic and niche fragrances with verified demand

Final target: 150 live fragrances.

## Data pipeline

Candidate -> identity verification -> fragrance metadata -> relationship review -> image source -> merchant offers -> QA -> live catalog.

For each canonical product, capture at minimum:
- product_id
- brand
- canonical_name
- concentration
- volume
- target_group
- main_accords
- short_description
- price semantics
- image
- in_stock semantics

Additional recommendation metadata:
- freshness
- sweetness
- woodiness
- spiciness
- longevity
- projection
- cluster_id
- relationship_role
- relationship_links
- evidence_confidence

## Immediate execution order

1. Create the Wave 1 candidate dataset without polluting the live catalog.
2. Verify exact product identity, concentration, and sensible canonical size.
3. Add women-specific recommendation behavior/tests before activating the women's batch.
4. Activate Wave 1 in small QA batches rather than all 40 at once.
5. Replace manual merchant mapping with approved affiliate feeds as soon as programs are accepted.
6. Use analytics/no-result queries to drive Waves 2 and 3.
