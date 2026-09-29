# DUFYND catalog readiness — 2026-09-29

Read-only snapshot from the repository data and promotion checks. This does not authorize a catalog write or publication.

| Measure | Current result |
| --- | ---: |
| Live fragrances | 33 |
| Staged candidates | 50 |
| Staged candidates with integrated merchant offers | 23 |
| Staged candidates with a current affiliate offer | 0 |
| Staged candidates with an approved-image status | 1 |
| Technically ready in the promotion dry-run | 1 |
| Blocked staged candidates | 49 |

Live audience assignments: men 32, unisex 17, women 2. Staged audience assignments: men 18, unisex 11, women 24. Assignments overlap and do not sum to product counts.

The readiness report lists 49 missing approved images, 32 missing current purchase destinations and 3 provisional community-data blockers. A product can have more than one blocker. The next ten-product planner selects one technically ready candidate and nine blocked candidates; the most immediate portfolio gap remains women's coverage.

## Technically ready candidate requiring review

`SC-LANCOME-LA-VIE-EST-BELLE-EDP-100` (Lancôme La Vie est Belle Eau de Parfum 100 ml) passes the current single-product dry-run with one non-affiliate purchase offer and no blocker. Its staged image is marked `approved_licensed_image` with a CC BY-SA 3.0 attribution record and an external image URL. That staging flag and the dry-run do not replace final visual-identity and image-rights review. The five-product release manifest remains a separate guarded batch. No product was promoted during this check.

## Reproduce from the repository root

```sh
python -m scripts.report_scentai_merchant_coverage
python -m scripts.plan_scentai_promotion_batch --limit 10
python -m scripts.report_scentai_promotion_readiness
python -m scripts.promote_scentai_catalog --product-id SC-LANCOME-LA-VIE-EST-BELLE-EDP-100
```

The final command is a dry-run by default. Read-only reporting does not need the agent runtime; an actual guarded write still runs staging recommendation QA and retains its approval gates.
