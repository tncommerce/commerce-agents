# DUFYND P0 candidate review checkpoint · 25 September 2026

All four remaining P0 fragrances now have a neutral, inactive candidate asset. None is activated as product truth. Promotion still requires direct exact-reference side-by-side QA.

| Product | Candidate | Current gate | Primary blocker |
| --- | --- | --- | --- |
| Prada L'Homme EDT 100 ml | `examples/retail/review-assets/product-candidates/prada-lhomme-p0-v5.webp` | Pending exact-reference QA | Confirm bottle proportions, cap/neck geometry, mirrored face, Saffiano placement and front branding against the exact 100 ml reference. |
| Giorgio Armani Stronger With You Intensely 100 ml | `examples/retail/review-assets/product-candidates/armani-swy-intensely-p0-v3.webp` | Pending exact-reference QA | Refined after side-by-side review. Final human approval still needed for cap sphere/ring geometry, shoulder width and typography. |
| Sospiro Vibrato 100 ml | `examples/retail/review-assets/product-candidates/sospiro-vibrato-p0-v2.webp` | Pending exact-reference QA | Refined after side-by-side review. Final human approval still needed for cap sculpture, plaque scale/position, emblem detail and silhouette. |
| Creed Absolu Aventus 100 ml | `examples/retail/review-assets/product-candidates/creed-absolu-aventus-p0-v1.webp` | Pending exact-reference / variant gate | Creed's current 100 ml page still shows imagery marked 75 ml, so the candidate deliberately avoids a visible volume marking until variant ambiguity is resolved. |

## Safety status

- Candidates live only under the internal repo path `examples/retail/review-assets/product-candidates/` and are not emitted by the storefront static export.
- The live source catalog, generated storefront catalog and structured visual metadata do not reference these candidate paths.
- Pending candidates are deliberately kept outside `storefront-web/public/`; passing fidelity review is required before a selected asset can be promoted into a public product-truth path.
- A regression test now fails if a candidate is accidentally promoted before review.
- Candidate masters are portrait, at least 1000 × 1200 px, and preserve full-bottle safe area.
- The existing live editorial images remain unchanged until a candidate explicitly passes the fidelity gate.

## Reference pages

- Prada L'Homme EDT 100 ml: https://www.prada.com/de/de/p/lhomme-prada-edt-100-ml/2A1251_2HC0_F0Z99_P_ML100
- Stronger With You Intensely 100 ml: https://www.armanibeauty.de/dufte/herrenduft/stronger-with-you/stronger-with-you-intensely-eau-de-parfum/ww-00180-arm.html?dwvar_ww-00180-arm_size=100ml
- Sospiro Vibrato 100 ml: https://sospirointernational.com/products/vibrato
- Creed Absolu Aventus 100 ml: https://www.creedfragrance.de/p/absolu-aventus/16281794/?variation=16281796

These pages are fidelity references only; they do not grant rights to republish manufacturer imagery.

## 15:57 refinement pass

- **SWY V3:** visibly closer to the current 100 ml reference than V2; candidate stays inactive because the remaining uncertainty is now in small cap/ring and proportion details rather than the overall bottle concept.
- **Vibrato V2:** visibly closer to the current official bottle than V1; candidate stays inactive because the remaining uncertainty is in the exact gold-cap sculpture, medallion scale/placement and emblem fidelity.
- **Prada V5:** remains a strong inactive candidate; side-by-side comparison still shows small proportion/detail uncertainty, so no verified promotion.
- **Creed Absolu V1:** remains blocked by current official size-image ambiguity; no verified promotion.
