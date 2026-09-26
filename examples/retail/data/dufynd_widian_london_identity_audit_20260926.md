# DUFYND Widian London identity audit — 2026-09-26

## Current DUFYND identity

- Product ID: `SC-WIDIAN-LONDON-EXTRAIT-50`
- Brand: Widian
- Product: London
- DUFYND concentration: `Extrait de Parfum`
- Volume: 50 ml

Both `scentai_products.json` and `catalog.json` currently carry this identity.

## Current external evidence conflict

A current German retailer listing observed on 2026-09-26 describes Widian London 50 ml as **Eau de Parfum**.

The official Widian site currently exposes London as a Sapphire Collection fragrance and an official `/en/products/london` route, but the retrievable official page content used in this audit does not expose an unambiguous concentration label.

Therefore the retailer wording is not sufficient evidence to rewrite the canonical DUFYND concentration.

## Decision

Status: `identity_concentration_review_required`

Until an official/primary source or exact authorized product document clearly confirms the concentration:

- do **not** add a merchant offer to `SC-WIDIAN-LONDON-EXTRAIT-50`,
- do **not** reinterpret an Eau de Parfum retailer listing as an Extrait listing,
- do **not** rename the live DUFYND product,
- do **not** change its product ID,
- do **not** use concentration-specific claims in new commerce copy.

Existing editorial/social content is not proof of the retail concentration.

## Unblocking evidence

Any one of the following is sufficient for a new review:

1. official Widian product page exposing concentration,
2. official Widian product sheet/catalog for the exact London 50 ml variant,
3. authorized distributor documentation tied to the exact product/EAN,
4. manufacturer response confirming the current concentration.

Product truth takes priority over obtaining an additional purchase destination.
