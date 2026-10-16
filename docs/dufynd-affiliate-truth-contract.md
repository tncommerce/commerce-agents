# Evidence-bound affiliate truth (development proposal)

## Problem and integration

Legacy `dufynd_affiliate_partners.status`, `feed_ready`, `tracking_ready`, repository
snapshots and `affiliate.status` can disagree. Reading a row today does not make
its original network evidence current. The existing top-Parfümerie worker is not
a general nine-partner state contract.

`DufyndJarvisBridge.load_context()` now adds `affiliate_truth` using a pure Python
projection. It reads existing partner rows and the optional existing master-status
key `affiliate.partner_evidence.v1`; it creates no service/table/RPC and performs
no writes. The runtime must use the generated `commerce_plan` as its eligible
partner list. Rejected/unknown/held partners are absent from that plan. Every
partner has `automatic_application_allowed=false` and `activation_allowed=false`.
Existing tools do not submit partner applications. This is a planning contract,
not a substitute for credential isolation or release authorization.

## Envelope and evidence

The existing master-status value is `{ "version": 1, "records": [...] }`.
Each strict record requires `merchant_id`, `status`, timezone-aware `verified_at`,
`source_kind` and a non-secret `evidence_ref` (`repo:`, `db:`, `mail:`, `network:` or
`owner:` reference). Optional `expires_at` can shorten validity. Do not store mail
bodies, tokens, account credentials, tracking secrets or OAuth URLs here.
`source_kind` is an attestation by the trusted operator/importer, not automatic
authentication of a supplied claim. An eventual ingestion path must verify it.

Positive state evidence expires after 30 days; feed/offer evidence after 72 hours
or the explicitly shorter expiry. These conservative development policy values
are not a claim about a network's actual approval expiration. `observed_at` never
refreshes `verified_at`. Future, malformed or conflicting same-time positive
facts fail closed. Each stage exposes its original reference/time and stale flag.
The paginated runtime context omits the volatile observation clock, so unchanged
evidence pages retain stable hashes; crossing a freshness boundary changes the
projection and correctly requires restarting the section.

## State prerequisites

| Stage | Required evidence |
| --- | --- |
| APPLIED / PENDING | Explicit fresh source evidence; no inference from silence |
| APPROVED | Separate network, network-email or verified-project approval; never feed access or a merchant feed letter |
| FEED_READY | Approval plus fresh verified feed; a fresh download alone is not row freshness |
| TRACKING_READY | Approval and fresh exact product/GTIN tracking plus verified landing; feed strategy additionally requires fresh feed |
| PRODUCT_READY | Same GTIN, published page, explicit release approval and explicit image-used declaration |
| REVENUE_READY | Product + tracking + fresh publicly verified in-stock offer with exact GTIN, price and shipping; if an image is used, matching asset-specific rights |

The stage order is conceptual: a verified product deeplink does not require a
feed. Revenue readiness means a technical purchase path, never proven sales or
an authorization to publish. Exact variant identity must have been established
by the verifier; the contract enforces matching product ID/GTIN across stages.
Image-free release is permitted only when explicitly declared, never inferred
from a missing image field. A rights hold cannot be cleared by forwarding a mail.

REJECTED is sticky when recorded by the legacy registry; reconciling that registry
requires explicit review outside this projection. A source rejection also blocks
unless superseded by a newer independent approval. Owner-only rejection hints
produce EXTERNAL_HOLD, not a fabricated network rejection. Explicit external holds
remain until reviewed and removed from the evidence set. Stale negative evidence
still blocks; expiry must not silently turn rejection into approval. Unknowns
never become approved from legacy positive flags.

## Rollout boundary

This PR does not backfill production evidence or change legacy rows. Without the
normalized evidence key, legacy positive states project UNKNOWN and legacy
rejections remain REJECTED. Therefore review/backfill is required before relying
on the projected eligible plan in an activated commerce worker. Evidence research
remains possible. No schema migration is needed or applied. The overnight audit's
partner table is a reconciliation proposal, not a production write.

Tests cover every transition, stale/future/malformed evidence, contradictory
facts, rejection suppression, image-free vs unlicensed assets, feed independence,
strict booleans and the actual bridge context integration. No external requests
or production mutations are made by the projection.
