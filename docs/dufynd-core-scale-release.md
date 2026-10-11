# Core-scale release

The same `QualifiedProductPage` renders private review routes and authorized public routes. The independent profile projection contains no price, merchant, community metrics or product photo. `LIVE_FRAGRANCES` appends only the generated authorized projection; catalogue search, public brand counts and product URLs therefore grow together.

## State machine

`FACTS_QUALIFIED → VARIANT_CHECKED → VISUAL_READY → FUNCTIONAL_QA → OWNER_REVIEW → PUBLIC_RELEASE`

`release-gate.mjs` is authoritative. A historical `owner_release_approved` boolean in the pilot manifest cannot enable publication. The gate requires matching fact, render and browser-evidence SHA256 values. A render digest includes shared renderer source, CSS, all qualified facts and the review manifest, so changed related profiles also invalidate old approval. QA must pass at 320, 390, 768 and 1440 pixels. Duplicate product IDs, slugs, approvals and QA rows fail closed.

An illustration can be technically ready without its design being owner-approved. Original-photo rights remain a separate HOLD even after illustration acceptance. Merchant availability is not a gate. BOSS Bottled Absolu is excluded from the candidate wave because its manufacturer's concentration statements conflict.

## Owner decision and integration

The exact candidate IDs and evidence hashes are in `examples/retail/data/dufynd_core_scale_release_decision.json`. Approve individual IDs or the named wave; do not infer approval from silence. For each accepted ID, append to `dufynd_release_authorizations.json` an approval with:

- `product_id`, `evidence_sha256`, `render_sha256`, `qa_sha256`: exact values from the decision record;
- `variant_approved`, `illustration_approved`, `publication_approved`: explicit owner decisions;
- `approved_by`, `approved_at`, `approval_reference`: the actual owner and durable decision reference;
- `indexing_approved`: separate indexing decision, false unless expressly approved.

No code changes, database write, new merchant integration or manual route creation are needed. `npm run build` regenerates only approved public profiles, includes their regular `/duft/[slug]` routes and catalogue cards, and uses the same qualified template. Only individually indexing-approved routes enter the sitemap. Public deployment and merging still require their own owner GO; a build is not permission to deploy.

Never put fixture approvals into the real authorization file. `test-release-gate.mjs` uses in-memory fixtures. A stale or incomplete approval with publication enabled stops the build rather than silently publishing or silently excluding an approved product.

## Reproducible QA

From `examples/retail/storefront-web`:

```bash
DUFYND_CATALOG_REVIEW=1 npm run build
# Start scripts/serve-static-export.mjs locally, then:
QA_BASE_URL=http://127.0.0.1:3013 QA_OUTPUT=/absolute/qa node scripts/catalog-release-qa.mjs
QA_BASE_URL=http://127.0.0.1:3013 QA_OUTPUT=/absolute/qa node scripts/brand-pages-qa.mjs
```

After all checks succeed, retain `release-qa.json` as `dufynd_release_qa.json` and run `node scripts/prepare-release-decision.mjs`. This records evidence only and grants no approval. Normal builds omit every review route. The four existing approved original photos retain their asset/variant bindings; the rights queue identifies each remaining exact product and its missing evidence. Existing affiliate-image licence scope does not automatically cover unrelated manufacturer images or an arbitrary current retailer URL.

## Brands and SEO

`/marken` and `/marken/[slug]` use normalized aliases and public-only counts. Brand pages reuse the catalogue's search by name, brand, concentration and documented notes. They remain noindex and absent from the sitemap in this revision. Reviews remain noindex/nofollow without canonical URLs; released profiles get their exact concentration/volume-specific canonical path. No unlicensed community figures or invented popularity order are introduced.
