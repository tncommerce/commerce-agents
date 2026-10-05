# DUFYND Social Publish Quality Gate V2

Purpose: no social post may reach scheduling/publishing merely because media and copy exist.

## Hard gates

A candidate reaches owner approval only when all of the following are evidenced:

1. Product truth and exact variant match.
2. Rights and factual-claim review pass.
3. Final upload asset digest is frozen and matches the reviewed asset.
4. Visual quality is at least 9.5/10.
5. Final media is at least 1080 px on both axes.
6. Native mobile preview is verified for crop, safe zones, readability and compression.
7. Platform click path is real:
   - Instagram feed/reel/carousel: do not treat caption URLs as clickable. Use verified profile-link CTA.
   - Instagram Story: a verified link-sticker path may be used.
   - TikTok without a clickable website surface: no raw URL CTA; use engagement/profile CTA only.
   - YouTube: video required; CTA must use an actually supported clickable/profile surface.
8. Owner approval remains separate. Passing QA never authorizes scheduling or publishing.

## Incident rule

If a live post fails any hard gate after publication, treat that publication as an invalid launch attempt for creative-quality evaluation. Preserve analytics evidence, but do not use the attempt as the clean baseline for the replacement creative. The replacement receives a new content revision/identifier and a fresh owner gate.

## Current remediation

The 2026-10-05 1 Million Instagram image post exposed two failures:
- final live image quality was below the Owner standard;
- a raw caption URL was presented even though that is not a clickable Instagram feed surface.

The scheduled TikTok sibling was stopped before auto-publish. Any replacement must pass this V2 gate before it can be presented for Owner approval.
