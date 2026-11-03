# Four additional exact Top Parfümerie offers · 26 October 2026

Four existing public DUFYND profiles gain a source-verified merchant offer in development. This extends the previous six-product Top scope to ten exact routes, preserving all 59 prior offer rows, all 106 prior mappings, the six original Top routes and the cheaper Perfumetrader Rabanne offer. It adds no profile, image approval, SQL write, runtime setting or production deployment.

| Existing profile | Selected merchant SKU / GTIN | Observed total including DE shipping | Variant caveat |
| --- | --- | ---: | --- |
| Montblanc Explorer EDP 100 ml | 849457 / 3386460101035 | 113.00 EUR | Select 100 ml at the merchant; initial page selects 30 ml |
| Creed Aventus EDP 100 ml | 827407 / 3508441001114 | 354.00 EUR | Select 100 ml at the merchant; initial page selects 50 ml |
| Prada L'Homme EDT 100 ml | 815682 / 8435137749607 | 117.95 EUR | Select 100 ml at the merchant; initial page selects 50 ml |
| Xerjoff Naxos EDP 100 ml, Gift Box | 836129 / 8033488155070 | 242.00 EUR | The offer explicitly retains “Geschenkbox”; no claim about unlisted additional contents |

The actual loaded merchant browser showed the selected size, exact SKU, price, availability and enabled visible purchase button on 26 October between **16:16:31 and 16:19:15 Berlin**. No basket or affiliate route was clicked. Existing same-day shipping evidence states Germany only, free shipping from 49.95 EUR and otherwise 4.99 EUR. All four observed prices exceed that threshold.

Naxos is named “EdP Spray Gift Box” by the source. The gallery showed the Naxos bottle and standard tall tricolour 1861 carton marked 3.4 FL.OZ. It did not show a candle or another item. The description does not enumerate the box contents, so neither the data nor the review asserts a candle bundle or bare-bottle packaging. The visible offer label preserves the source packaging distinction.

## Source binding

The official Awin source run [40347496483](https://github.com/tncommerce/commerce-agents/actions/runs/40347496483), on development commit `afda17e192b2bfa93b526111ad340ae20e9b9794`, checked active membership for advertiser31081/feed91379 at15:15:27UTC. It used the existing free public Ubuntu source job, with0billable runner milliseconds and no artifact/cache upload. The feed SHA-256 remains `669e9fc954c44f84d13db4aa4f0ec3f7459ff5923939bae0fda119a426fcaf5d`.

The four URLs are the exact original Awin `pclick.php` product links. None was synthesized, rewritten or followed. The existing route validator binds product ID, merchant SKU, Awin product ID, advertiser, publisher, feed and target URL. No validation or publication safeguard was changed.

Current feed fields do not contain GTIN, size, stock or shipping. `merchant-browser-observations.json` supplies current selected variant and purchase facts; `identifier-corroboration.json` supplies independent product identifiers. Prada also has the current manufacturer identity in `prada-manufacturer-identity.json`. Image filenames alone are not GTIN proof. Existing Top feed-material rights and written permission are inherited from the prior six-offer package; no additional license is claimed.

## Actual integration and tests

- Canonical offer data:59→63 rows; the previous59 rows are unchanged.
- Canonical mappings:106→110; the previous106 are unchanged.
- Top verified route scope:6→10, preserving the previous6 exactly. The merchant homepage affiliate route stays disabled.
- Existing approved/public image registry and all37 profiles are unchanged. The four new original-photo candidates remain pending human visual approval in their separate review packet.
- The normal `prepare_dufynd_runtime_offer_batch` CLI, without `--apply`, accepted all4 real canonical routes. Batch `top-wave2-20261026T151915Z`, SHA-256 `ef5d1eba49e49980f6c43a062069594d69bf8850417c8653194fc2c6e4296973`.
- Twelve targeted tests passed:8new source/store/route/preservation/expiry tests, the affected previous six-wave preservation test,2exact mapping tests and the affected queue source-fingerprint contract. Ruff and `git diff --check` passed. This is offline targeted verification, not full CI or a live clickout.
- The normal static store and customer payload expose each exact total and qualifier. A pure in-memory resolver returns the original tracked target. The72-hour expiry works. Explicit Top runtime scope still fails closed without database evidence.

The common source freshness boundary is **29 October2026 at16:16:31.046 Berlin** (`2026-10-29T15:16:31.046Z`). Do not extend timestamps without new actual source observations. An initial static-data release needs no runtime SQL; if the actual deployment explicitly assigns Top to runtime scope, that existing requirement must be checked before release.

Production release remains subject to the coupled release gate. Original-image publication is a separate pending visual approval; these offer rows do not approve or expose those four images.
