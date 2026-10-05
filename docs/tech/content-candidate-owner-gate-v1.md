# Content Candidate Owner Review V1

The existing content asset register now connects an internally ready candidate to an
idempotent pending decision in dufynd_human_decisions. No existing asset is backfilled
and no today-post, scheduling, product activation or external publishing is modified.

An asset insert/update runs the bounded preflight. The owner_review_v1 packet must contain
product/product_id, hook, full caption, platform, timezone-qualified future requested_at,
content_id, experiment_id, internal_rating (9.5–10) and recommendation reason. Its identity
must match the asset register's content, platform, product and campaign. The asset must have
explicit quality/visual/rights/product-match/destination pass evidence, a matching reviewed
SHA-256, an evidence reference and distinct declared creator/internal-reviewer identities.
These declarations do not certify a new critic worker. Final independent Owner review is
still required; no worker is given publishing or approval-resolution capabilities.

The decision binds the exact asset record/version/URI/metadata fingerprint. Editing the
record supersedes pending/approved decisions for the old fingerprint, even when the new
revision fails preflight. A score never bypasses a failed hard check. Duplicate requests
for an unchanged record do not create duplicate decisions. The current exact First-Money content ID is explicitly protected today.

The Control Room reads fixed scalar projections only. Creative is an asset ID plus revision
fingerprint; no asset URI or signed URL is sent to the browser or fetched automatically.
Captions can show bounded canonical DUFYND acquisition links as text, but other URLs,
session parameters, credential-like content and configured secrets are restricted.

The dashboard remains GET-only with no release, schedule or publish button. The GO token
is a review identifier, not an executable social authorization. Scheduling and publishing
remain false even if a database decision is later marked approved.

Tests use a declared Delina fixture in a rolled-back transaction, covering automatic gate,
dedupe, revised/failed-rights invalidation, missing review evidence, self-review and quality
failure, plus public-role denial. No real Delina asset or decision is created. Four-width
isolated browser replay validates complete decision details and zero-gate UI semantics.
