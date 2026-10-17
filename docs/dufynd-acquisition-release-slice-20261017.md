# DUFYND — RC1 Acquisition Release Slice / Draft 42

**Stand:** 17. Oktober 2026. **Status:** DRAFT, NOT LIVE, NO MERGE/DEPLOY AUTHORIZATION.
**Base:** `scentai-mvp` at `2868882d337244a7d4f0c3ac8b7c51ef9f9d5e7e`.
**Provenance:** only the independently tested RC1 catalog acquisition and truthful
editorial social metadata source from the large, unmerged PR #799 at
`ad6e2a945312da376a6f8ad47b64216c47cfc18a`. This is a new, isolated release candidate, not a visual launch.

## Intended user-facing delta

1. In the 37-fragrance catalog, cards without a verified published affiliate
   offer say **"Duftprofil entdecken"**, not "Duftprofil & Angebote ansehen".
   The exact `SC-RABANNE-1-MILLION-EDT-100` card additionally links internally
   to `/duft/rabanne-1-million#angebote` with **"Händlerangebote prüfen"**.
   No sale, stock, price, discount or additional approved partner implied.
   The existing attribution-aware internal-link component preserves consent
   and campaign context; no new merchant/clickout URL is introduced.
2. The exact Rabanne 1 Million EDT **100 ml** profile, and only in the absence
   of a verified reused product-photo source, uses an original abstract,
   *non-product-image* 1200x630 social OpenGraph/Twitter card. No brand-logo
   recreation, fabricated bottle, photo, review or offer fact. Rights-verified
   product photography would automatically take precedence; structured Product
   image data remains limited to its old verified-photo source.
3. Changes are localized to two components, one RC1-specific CSS appendix,
   two new social image-generation/test scripts, one responsive navigation QA
   extension and minimum necessary package script hooks.

## Isolation (strict)

DO NOT import the replacement hero `AtelierHero`, new Three.js object,
CGI shader experiments, the rejected 2011 Commons photo, licensed visual
research branch assets, editorials or other style/feature changes from PR #799.
DO NOT import Jarvis #800/#801/#802, SQL migrations, Control Room work,
content publishing, catalog draft waves, prices, Awin/Perfumetrader
destination changes, tracking consent changes or new paid services.

`package.json` keeps every production dependency and prebuild task from the
base exactly; only prefixes the two existing dev/prebuild scripts with the
self-contained 0-EUR RC1 social-card generator/test.

## Release gate and evidence

Upstream evidence: PR #799 [CI #39070518141](https://github.com/tncommerce/commerce-agents/actions/runs/39070518141)
SUCCESS 7/7; original QA artifact 12114972293 includes actual responsive
390/1440 RC1 catalog screenshots. These proofs are bound to **PR #799**, not to
this isolated slice. The new PR requires its **own exact-SHA full CI**, genuine
320/390/1440 browser screenshots where supported, search/offer/attribution/
Consent/SEO/partner-image guard regression, and independent visual inspection.
Never claim it has passed before the run and artifact are finished.

**Release hold:** Separate exact Owner approval is still mandatory for
mark-ready, merge, protected-branch write, production deployment, database
migration, social posting or affiliate change. If no further authorization
is available overnight, finish the draft, attach evidence and STOP at
NOT_FINAL_YET without requesting permission or inventing authorization.

## Post-release measurement (if separately authorized)

Compare qualified, consented sessions -> exact RC1 detail -> offer section ->
documented merchant_clickout and later verified partner-reported commissions.
None of these test steps represents proven revenue.
