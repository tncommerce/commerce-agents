# DUFYND P0 candidate review checkpoint · 25 September 2026

All four remaining P0 fragrances now have a neutral, inactive candidate asset. None is activated as product truth. Promotion still requires direct exact-reference side-by-side QA.

| Product | Candidate | Current gate | Primary blocker |
| --- | --- | --- | --- |
| Prada L'Homme EDT 100 ml | `/products/candidates/prada-lhomme-p0-v5.webp` | Pending exact-reference QA | Confirm bottle proportions, cap/neck geometry, mirrored face, Saffiano placement and front branding against the exact 100 ml reference. |
| Giorgio Armani Stronger With You Intensely 100 ml | `/products/candidates/armani-swy-intensely-p0-v2.webp` | Pending exact-reference QA | Confirm cast-iron-grey cap/ring geometry, shoulder silhouette, cognac tone and typography. |
| Sospiro Vibrato 100 ml | `/products/candidates/sospiro-vibrato-p0-v1.webp` | Pending exact-reference QA | Confirm sculpted gold cap, oval plaque geometry, emerald velvet texture and complete 100 ml silhouette. |
| Creed Absolu Aventus 100 ml | `/products/candidates/creed-absolu-aventus-p0-v1.webp` | Pending exact-reference / variant gate | Creed's current 100 ml page still shows imagery marked 75 ml, so the candidate deliberately avoids a visible volume marking until variant ambiguity is resolved. |

## Safety status

- Candidates live only under `/products/candidates/`.
- The live source catalog, generated storefront catalog and structured visual metadata do not reference these candidate paths.
- A regression test now fails if a candidate is accidentally promoted before review.
- Candidate masters are portrait, at least 1000 × 1200 px, and preserve full-bottle safe area.
- The existing live editorial images remain unchanged until a candidate explicitly passes the fidelity gate.

## Reference pages

- Prada L'Homme EDT 100 ml: https://www.prada.com/de/de/p/lhomme-prada-edt-100-ml/2A1251_2HC0_F0Z99_P_ML100
- Stronger With You Intensely 100 ml: https://www.armanibeauty.de/dufte/herrenduft/stronger-with-you/stronger-with-you-intensely-eau-de-parfum/ww-00180-arm.html?dwvar_ww-00180-arm_size=100ml
- Sospiro Vibrato 100 ml: https://sospirointernational.com/products/vibrato
- Creed Absolu Aventus 100 ml: https://www.creedfragrance.de/p/absolu-aventus/16281794/?variation=16281796

These pages are fidelity references only; they do not grant rights to republish manufacturer imagery.
