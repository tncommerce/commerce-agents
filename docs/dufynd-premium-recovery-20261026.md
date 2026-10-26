# DUFYND catalogue first-fold recovery — 26 October 2026

Development-only continuation of PR #836, parent `016d3fde7fd1a22a1402e8d70a35ac2456a3bc8a`.

The original-photo result cards previously put a 280–300 px photograph before the readable product identity. At 768 px the first name was below the initial 1000 px view. The catalogue now places the unchanged approved photograph beside the brand, fragrance name and exact concentration/volume. Two columns remain readable at desktop; unapproved-photo entries retain their existing honest text treatment. The A–Z brand directory follows the results (and remains available after an empty search); the existing brand filter remains above them. No homepage, product-detail, image-registry, consent, offer or tracking implementation changed.

## Actual local validation

- Complete retail Next build: TypeScript, 105 generated routes and all existing pre/postbuild checks, including private-photo/review-route separation and 55 static metadata checks.
- Existing Visual Reset Python source suite: 6 passed.
- Existing mobile-discovery browser suite extended to 320, 390, 768, 1023, 1024, 1440 px: 84 scenarios. Includes the first readable product name and exact variant, filter disclosure, search/focus, two comparison selections and context return, empty/error/wrong-product/synthetic-available offer states, and missing/failed images.
- Separate first-fold checks at 844 px phone height and 1000 px tablet/desktop height, including the brand directory after an empty search.
- 15 actual editorial browser captures: homepage, catalogue, Black Opium at 390/768/1023/1024/1440. 200 responses, no horizontal overflow, no JavaScript errors.
- Local Chromium 140 / Playwright 1.55.0. API replies are isolated fixtures. Existing original-photo URLs were downloaded unchanged into a private local cache and fulfilled as image-only fixtures, because direct browser egress is unavailable in this runner. Images were decoded successfully; this is not a new photo-rights grant or a claim of current merchant prices.
- The shared test helper now waits for hydrated measurement controls or the saved choice. Previously an SSR `unknown` state could race a persisted denial and attempt to click an already-removed button. Production consent behavior is unchanged.

| Width | First result top before → after | First name bottom after | Exact variant bottom after |
|---:|---:|---:|---:|
| 390 | 751 → 683 px | 781 px | 830 px |
| 768 | 721 → 675 px | 773 px | 822 px |
| 1023 | 721 → 675 px | 756 px | 805 px |
| 1024 | 863 → 817 px | 898 px | 947 px |
| 1440 | 811 → 765 px | 866 px | 915 px |

Before/after uses the same current PR baseline and viewport, not a theoretical mockup. Review HTML and source-hashed browser evidence are delivered privately with this work. Four approved original photographs remain a material visual-coverage limit for 37 profiles. No claim of 9.5/10 or Owner acceptance.

## Release boundary

No GitHub Actions were dispatched, and these local checks are not full CI. No production merge, deployment, database migration, affiliate activation, real clickout or analytics/conversion event. Commit uses `[skip ci]`; all publication and production decisions remain separate Owner gates.
