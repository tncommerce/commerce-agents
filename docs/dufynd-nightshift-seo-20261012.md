# Catalog metadata correction — 2026-10-12

Scope: development PR #774 only. No merge, deployment, new profile, image,
merchant offer, indexing approval, or release receipt modification.

The released-profile branch of `generateMetadata` returned product-level
`indexing_approved` and `follow: true` even when the global
`NEXT_PUBLIC_SITE_INDEXABLE` gate was false. The page-level robots value could
therefore override the preview site's default noindex metadata. That branch also
omitted Open Graph and Twitter overrides, leaving homepage social metadata to
describe a specific fragrance.

It now requires both global and product indexing approval, respects the global
nofollow/nocache preview setting, and supplies the exact product title,
description and canonical URL for social previews. No photo is inferred from an
illustration or a source hold: social image arrays remain empty and Twitter uses
the summary card.

An offline behavioral regression invokes the actual exported metadata function
using synthetic profiles and all four approval combinations. It failed on the
previous implementation and passes with this change; no HTTP, analytics event,
browser visit, or real release authorization is created. The test runs in the
existing prebuild hook. Existing release-gate checks and six SEO tests also pass.
The design renderer digest and Owner approval files are unchanged.

Remaining distinct observations (not silently repaired): the qualified renderer
still describes its neutral studio card as a vector illustration in its source
details, and its public branch has no product-detail analytics component. Those
are renderer-bound changes requiring a separate candidate and refreshed QA and
Owner review receipts before any release; existing approvals are not rewritten
to bless them. They do not affect the currently live isolated Rabanne RC1 page.

## Development-only RC1 ancestry integration

Merged the released `d3e948ebeb22c944ad143b20e644d0c0c5f4b186` history into this Draft branch. The dynamic route continues delegating to the existing `FragranceDetailPage`, preserving the qualified catalog routing and reviewed-profile gates. The shared offers component keeps the broader development safeguards: comparison badge only for multiple offers, explicit listed-offer scope, total-price basis and neutral shipping text. These cover RC1 focused-landing behavior without reverting the rest of the catalog. The RC1 visual-QA stage selector correction and isolated stylesheet are retained. No reviewed renderer, receipt, production branch or release approval was modified.

The existing exact-variant feed matcher was shared with the narrow photo Draft #776. Both branches now reject duplicate numeric merchant SKUs before filtering image URLs, including name-only discoveries. Synthetic tests cover missing, disallowed and valid duplicate image URLs in both row orders; no feed download, image registration, offer change or publication occurs.
