# DUFYND discovery release

Product facts, visuals, publication and affiliate offers are separate decisions.
`dufynd_discovery_qualification.json` remains the source for 28 qualified staging
records; manufacturer references are not GTINs. No new canonical rows are added.

## Prepare a wave

1. Verify the exact brand, fragrance, concentration and volume against the cited
   product page. Add only independently supported product facts and descriptions.
2. Add a pilot to `dufynd_release_pilots.json`, including `expected_variant` and the
   SHA256 from `evidence_digest`. Changed facts require a fresh review.
3. Select an approved, exact-variant photo from the existing rights registries or
   the original `ScentArtwork` vector composition. The latter carries the visible
   label “Duftillustration · kein Produktfoto”, uses no external asset and contains
   no reconstructed bottle. A photo's fidelity metadata alone is not a licence.
4. Run `python scripts/report_dufynd_discovery_release.py`. This read-only command
   reports factual readiness and the owner gate. It never publishes or modifies data.
5. Build locally with `DUFYND_CATALOG_REVIEW=1 npm run build` in the storefront.
   Review routes are `/review/duft/<manifest slug>` and carry noindex. Run
   `scripts/catalog-release-qa.mjs` against the local static server and inspect
   real screenshots at 390 and 1440 pixels, plus responsive checks.
6. Obtain an explicit owner decision on the exact evidence digest and design before
   creating public routes. The report's eligibility flag is not a deployment action.
   These pilots are not connected to the public catalogue or sitemap. A normal
   build deletes review exports, including stale files from a previous review build.

Affiliate offers do not determine eligibility for a factual fragrance page. Add
an offer only through the existing exact-variant merchant verification and
tracking gates. The pilots include no prices, availability or affiliate links.

## Public data boundary

`generate-public-fragrance-data.mjs` creates client-safe data before build/dev.
Unlicensed third-party rating counts, ratings, ranks, longevity and projection
metrics are excluded before bundling, including legacy catalogue attributes.
A clean build removes disposable `.next`/`out` outputs so old chunks cannot retain withdrawn metrics. Private source data stays intact. Homepage API records are also sanitized before
rendering. No permission is inferred from public accessibility or “provisional”.
Numeric community sorting is unavailable and old rating-filter links are cleared.
Qualitative discovery and existing DUFYND scent-profile filters remain available.

The live Supabase checkpoint `catalog.parfumo_community_data_rights_gate_20261010`
was read with SELECT on 2026-10-11: no proven commercial rating licence; source
rights evidence pending. No SQL writes were attempted in this continuation.
This branch prepares the mitigation; production remains unchanged until owner GO.

## Current pilot evidence

| Pilot | Identity | Original photo | Review visual |
| --- | --- | --- | --- |
| Prada Paradoxe EDP 90 ml | 1A1351_2HDZ_F0Z99_P_ML090 | Commons licence documented; photographed 90 ml size unproven | Original CSS illustration |
| Prada Paradigme EDP 100 ml | 2A1451_2H0Q_F0Z99_P_ML100 | No asset-specific reuse grant established | Original CSS illustration |
| REPLICA By the Fireplace EDT 100 ml | MM005 + explicit 100 ml bottle selection | No asset-specific reuse grant established | Original CSS illustration |

All three are manufacturer references, not verified GTINs. Original manufacturer
URLs are retained in the fact records and visible on each pilot page. The Paradoxe
Commons candidate remains HOLD. Zero additional original-photo rights are claimed.
Four previously approved photographs remain in use, matched by product, URL and
volume against the existing candidate registries. Other catalogue cards use the
labelled illustration in this draft, not blank cards or artificial product scenes.

The existing 28 records remain 24 manufacturer references and four verified GTINs.
Thirteen pages are prepared for owner review, zero additional pages are publicly
released. PR #774 remains draft; PR #759/#773 and all deployment gates remain HOLD.

## Scalable review waves

The manifest contains 13 complete variants: the three original pilots plus Good
Girl EDP 80 ml, Coco Mademoiselle EDP 100 ml, Eros Pour Homme EDP 100 ml, Nomade EDP
75 ml, Flora Gorgeous Gardenia EDP 100 ml, Mon Guerlain EDP 100 ml, Baccarat Rouge
540 EDP 70 ml, Born In Roma Donna EDP 100 ml, Alien EDP 90 ml and Goddess EDP 100 ml.
Twelve use manufacturer references; Good Girl uses its previously verified GTIN.
They do not overlap the public catalogue. The other 15 qualified facts are not
silently promoted. Image HOLDs and existing fact-check dates remain unchanged.

`ScentStudy` replaces the three identical folds with six original vector
composition families. The lead pilots explicitly select blossom, architecture
and embers. Card selection uses note labels before a deterministic fallback.
The implementation loads no external artwork, WebGL or motion library. It uses
no continuous animation, and the page respects reduced-motion preferences.

Each entry declares an exact variant, source digest, motif and future SEO path.
Run `python -m scripts.prepare_dufynd_review_wave` only to bind new empty digests;
the command never changes an existing digest or an owner gate. The server build
rejects changed evidence, duplicate IDs/slugs, public-product collisions and
invalid visual provenance. The readiness report remains read-only.

Future canonical paths include concentration and volume. They are plans, not
current public URLs. Review metadata has a unique factual title/description but
no public canonical and noindex/nofollow. Promotion must explicitly wire the
approved path into the public route/catalogue/sitemap generators; this review
wave changes none of those inventories. Public structured offers or ratings
must never be inferred from page availability.

The shared page preserves key-note lists instead of inventing a pyramid, labels
manufacturer and merchant identity sources separately, and exposes prior/next
navigation plus a full wave directory. Brand aliases normalize presentation
without changing product identity evidence. Public counts exclude validation
HOLDs and count only currently public entries, never staging/review entries.

CI first validates the normal public export and the existing browser regression,
then builds the opt-in review wave and checks every manifest route at four widths.
Local captures provide first-two-row catalogue views and real before/after pilot
comparisons. Adding a manifest entry expands browser coverage automatically.
