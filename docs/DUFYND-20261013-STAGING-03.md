# DUFYND-20261013-STAGING-03 — private manufacturer review

Base: `8647495e5619d1acfaa1346949d586e3b27c4fab` (production read-only).
Compared only the relevant intake contracts at Draft #774
`a21ebf53a812c32d1817a5ca9a8e5e88d8797f9e`; no catalog audit or source re-research.

## Implemented boundary

The existing `validate_dufynd_catalog_expansion_wave.py` requires merchant evidence
when product_data is present and rejects the three honest UNKNOWN affiliate states.
`build_scentai_catalog_staging.py` is an integrated catalog preparation pipeline, not
an appropriate facts-only store (it also has legacy community defaults). The #774
`catalog-growth.mjs` validator checks manufacturer facts against *already staged*
product IDs and requires its larger qualification/review pipeline. Neither contract
is weakened or replaced here.

New `scripts/prepare_dufynd_manufacturer_review.py` accepts only the existing three-record
GROWTH-02 packet, pinned by SHA256
`66b7e32c9415232b71fd2d7fac379a522be080386b5734143bc8843f3e54b76f`.
It verifies candidate identity against the existing registry and rejects collisions in
catalog, source products and staging by ID and exact normalized variant. Aliases PDM,
EDP and case/diacritics cannot conceal an existing duplicate; edition words are kept.
Valaya Exclusif stays a separate product. A changed source packet requires a separate
reviewed code update; this is not a generic importer that trusts any manufacturer URL.

Output contract: `dufynd.private_manufacturer_review.v1` with `records`, not public
`products` or legacy `candidates`. Each record retains source evidence/date, exact
identity, manufacturer notes and caveats, a deterministic review ID and fact SHA256.
GTIN stays null. It carries no price, inventory, community score, merchant URL, affiliate
link, image, website path or release authority. Every downstream gate is explicitly false.
Input/registry fingerprints make the basis of each receipt auditable.

Default execution validates and prints only a summary. Optional output must be outside
the checkout; it is atomically installed as a mode-0600 JSON receipt without overwrite.
Identical reruns return UNCHANGED. Conflicts, symlinks and nonprivate existing receipts
fail closed. No database, network client, scheduler, website route or exporter is invoked.
The private receipt is deliberately not committed to the public repository or uploaded
as a GitHub artifact. It is retained separately for the Owner's private review.

```sh
python scripts/prepare_dufynd_manufacturer_review.py
# Optional private output outside the repository, not a served website directory:
python scripts/prepare_dufynd_manufacturer_review.py --output /private-owner-path/review.json
```

## Actual processing and tests

Three records created, then rerun with result UNCHANGED; registered products=0.
Receipt SHA256: `6e00296001a991bdbb6c376e124b5ad9b9543e0924786cfa6e6cdabf17e8510e`.

| Candidate | Proposed ID, still unregistered | Private review | Catalog / public release |
| --- | --- | --- | --- |
| BDK Gris Charnel EDP 100 ml | SC-BDK-GRIS-CHARNEL-EDP-100 | ready | HOLD |
| Montale Arabians Tonka EDP 100 ml | SC-MONTALE-ARABIANS-TONKA-EDP-100 | ready | HOLD |
| Parfums de Marly Valaya EDP 75 ml | SC-PDM-VALAYA-EDP-75 | ready | HOLD |

80 targeted tests PASS: new source binding/variant/GTIN injection checks, candidate
and registry drift, ID/variant duplicate prevention, Valaya Exclusif distinction,
concurrent creation, interrupted write/retry, conflict preservation, output permissions,
and unchanged expansion, staging/promotion and licensed-image release gates.
Local tests use `--confcutdir=tests` because unrelated root fixture dependencies are not
installed; the normal new-commit CI still executes its full configured checks.
Ruff check/format PASS. No frontend change or browser PASS claimed by this task.

The original GROWTH-02 packet still fails the old importer with exactly the same three
`invalid_affiliate_state` errors. The private receipt itself fails it with
`wave_has_no_candidates`. Thus private preparation does not silently authorize intake.

## Commercial follow-through: existing evidence only

Inspected the production repository's affiliate program/activation records, exact merchant
mappings, offers and approved-feed image candidates, plus existing Supabase keys
`affiliate.status` (evidence date 2026-10-01) and the top Parfümerie readiness/four-row
recovery checkpoints (2026-10-10). Read on 2026-10-13; these are historical observations,
not a fresh Awin account approval or live price/stock verification. No redirect was opened.
The four recovered Awin rows concern other products, not these three. No exact mapping,
offer or approved-feed image candidate for these three IDs was found in the checked records.
Valaya Exclusif mappings/offers are excluded; approval cannot transfer across variants.

All three have the **same proven publication-readiness tier: BLOCKED, no verified active
exact-variant affiliate offer**. There is no defensible revenue/demand ordering yet.

| Candidate | Existing merchant identity research | Missing commercial evidence |
| --- | --- | --- |
| BDK Gris Charnel 100 ml | Niche Beauty 873-008, exact EDP/100 ml research dated 2026-10-12; country availability text conflicts | Niche Beauty program relationship UNKNOWN in checked records; current purchasable exact offer, authorized tracking and receipt absent |
| Montale Arabians Tonka 100 ml | Douglas article 501346, exact EDP/100 ml research dated 2026-10-12; seller ambiguity | Douglas latest recorded application pending, not approved; actual seller, current offer and authorized exact tracking absent |
| Valaya 75 ml | Niche Beauty 651-035 exact EDP/75 ml research dated 2026-10-12; country-unavailable caveat | Niche Beauty relationship UNKNOWN; current exact offer and tracking absent. Douglas 30 ml evidence is not evidence for 75 ml |

For every candidate: source-supported identifier or exact merchant variant mapping,
current source timestamp/price/currency/availability, approved program, authorized
product-specific routing/attribution and activation approval must be separately evidenced.
GTIN remains UNKNOWN unless supplied by a legitimate exact-variant source. Image rights,
curated review presentation, renderer-bound QA and explicit product release remain separate
holds even if merchant readiness is later proven. Existing top Parfümerie or Perfumetrader
program approval alone does not establish these products' presence in their feeds.

## Deployment and resume

No merge, production deployment, database migration, registry/staging data edit, public
product or indexable link. No costs, paid/model calls, artificial visits/clickouts, customer
contact or social publication. Main, PR #774/#779, Nightshift migration/manifest/two tasks,
Cron 11, Owner decision and pilot window are untouched. This is not a Nightshift action.

New PR contains only the isolated script, tests and this evidence note. Exact commit/CI
and private receipt identity are recorded in the PR and `ops.DUFYND-20261013-STAGING-03`.
Resume only if that run is incomplete; do not repeat GROWTH-02 or FUNNEL-01.

Next useful DUFYND task: a bounded read-only exact-variant lookup for these three products
in an already approved merchant's legally accessible feed, retaining UNKNOWN for absent
GTIN/stock/rights and creating no offer or clickout. This would resolve the next commercial
evidence gap without pretending manufacturer facts are merchant approval.
