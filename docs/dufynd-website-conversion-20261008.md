# DUFYND website conversion checkpoint — 2026-10-08

## Live evidence

- Repository branch `scentai-mvp`: `6bdf1f5f21aa1d0dc591756216a79d9d6800f48c` at checkout.
- Latest merged PR #744 head `344b420287bb6dc03085f2d0522e4371c980f2e8`: DUFYND CI run 37754241201 passed. The combined-status API returned no statuses for the merge commit; do not treat that as a green check.
- Open PRs at preflight: #739, #735, #685, #598 and draft #1. #735 and #739 concern main; untouched. This work targets scentai-mvp only.
- Render frontend `scentai`: live deployment dep-db27t2egekts739n81j0, commit `06879f45d530bae15c70565dc9d55bc4cb13955a` from October 6. API: live deployment dep-db3mqc3l550s73amske0 on current checkout commit. Frontend and API therefore do not share the same revision.
- Both dufynd.de and the Render frontend load. Desktop homepage and Naxos detail inspected; Naxos at 390×844 has loaded images and no horizontal overflow. Offers CTA appears at y=622 before this change. Naxos currently returns no sufficiently fresh verified merchant offers and exposes an official manufacturer fallback.
- Supabase DUFYND project ACTIVE_HEALTHY. Read-only query confirms continuity.tech_lease is released. No supervisor, budget, queue, schema or permission writes performed.

## Delivered change

Empty and failed offer states now offer an attributed catalog route. Product detail exposes the existing alternatives anchor only when related products exist. Manufacturer fallback, retries, price freshness and affiliate gates remain intact. Normal available-offer rendering is unchanged. Recovery actions have 44px minimum tap height.

Mobile product staging now uses a 220–304px responsive minimum rather than a fixed 304px minimum, preserving existing bottle assets and atmosphere while moving purchase actions earlier on small screens. No bottle geometry or image approval is changed.

## Prioritized remaining work

Validation: production build including TypeScript and all 70 static pages passed; three existing prebuild suites passed; five targeted Python offer/analytics/disclosure tests passed; nine isolated browser cases passed (empty, failed and available offers at 320, 390 and 1440px). Browser fixtures intercepted API calls, so tests created no live merchant clicks, paid advisor calls or analytics events. The new cases are part of the existing dufynd-visual-qa CI job; the feature branch starts with dufynd- so that job runs.

1. **P0 — offer availability and landing promise:** Naxos is the homepage spotlight but currently has no verified purchase offers. Revalidate exact merchant variants through existing offer/feed gates. Do not activate stale prices or merge mapping PR #598 as an assumed offer activation.
2. **P0 — deployment provenance:** verify PR CI on its exact head, then reconcile frontend deployment with accepted scentai-mvp. A successful local build is not proof of production rollout. Render auto-deploy is enabled on scentai-mvp; main remains owner-gated.
3. **P1 — product representation:** current source report has 35 visible products: 6 verified truth images, 29 editorial-only. All 35 have presentation assets, which does not establish exact product fidelity or third-party rights. Three candidates await their separate promotion/review gates; eleven release assets are blocked. Prioritize high-traffic products and exact size/concentration checks. Preserve existing provenance and attribution; manufacturer or affiliate identity alone does not grant image rights.
4. **P1 — spatial premium design:** retain approved product layer plus bottle-free atmosphere. True GLB activation requires existing rights and geometry gates. No inferred caps, false mesh bottles, unapproved assets or paid generation. Extend interactions only after mobile performance and reduced-motion review.
5. **P1 — dependencies:** npm audit reports existing high advisories for next 16.3.6, sharp 0.35.4 and source-map-js. Assess static-export exposure and patch in a separate dependency change with complete workspace validation. No automatic force-upgrade performed.
6. **P1 — measurement:** preserve acquisition source, campaign and content through recovery; measure product→offers→merchant behavior using existing analytics. No measured bounce-rate or revenue improvement claimed from this change.

## Content transfer engineering backlog

Source of truth remains the owner FINALs: `/DUFYND/Content System/2026-10-08/One Night Fourteen Fragrances/FINAL.png` (owner 9.5), `/Phone Suspicion Amouage Decision/FINAL.png`, `/Groceries Fragrance Meme/FINAL.png`.

Drive metadata confirms the exact `DUFYND_2026-10-08_Packing_14_Perfumes_FINAL.png` exists as a private image/png file (2,480,672 bytes). No new upload is required. No query-based replacement or new generation is permitted. Owner social approval covers exactly the packing FINAL for IG/TT on October 8.

The available Metricool scheduling contract accepts mediaFiles strings but exposes no authenticated private-Drive normalization/upload tool. Prior egress rejection is retained; no retry through public sharing, bearer URL, data URI, external upload or substitute media. Engineering acceptance: supported authorized private-file transfer; byte/hash identity preserved; owner FINAL mapped to exact IG/TT destinations; no duplicate scheduling; readback proof. Social publication is not claimed complete.
