# top Parfümerie feed evidence

The release checker includes up to ten normalized offer evidence records per
product, sorted by offer ID, with an explicit truncation flag. It records SKU,
variant label, feed price, currency, normalized stock, source timestamp, age and
all static eligibility blockers. Raw merchant and tracking URLs are omitted.
The existing read-only Awin workflow includes this output in its sanitized
`release-readiness.json` artifact; no workflow or credential change is needed.

Normalized stock is not an independent availability check. The current
top Parfümerie adapter defaults missing availability to false. Do not interpret
that value as proof that the merchant has sold out. Conversely, a merchant's
in-stock-only feed statement does not verify an exact landing-page variant.
Static eligibility never grants tracking, landing-variant or activation approval.

## Verified continuation checkpoint

- Repository base: `c5e55b0928647e2a288b75ccbfcd4ac2979c00e9`, `scentai-mvp`.
- Previous identity/freshness fix: PR #749, merged as
  `fd3a2485a8af0c6b36353841a11a7cccb0451af5`.
- Authenticated read-only feed run: `37865962641`, artifact `11588262093`.
- Artifact feed check: `2026-10-09T00:40:59.711175+00:00`, 7,904 rows;
  advertiser 31081, feed 91379, active membership.
- Four mapped Release 01 products: La Vie est Belle EDP 100 ml, Delina EDP
  75 ml, Black Opium EDP 90 ml and Libre EDP 90 ml. None is statically eligible.
- Hypnotic Poison EDT 100 ml is not mapped in that report.
- The downloaded artifact contains counts, not the four raw prices, SKU/GTIN
  evidence or redirect chains. No current prices or exact stock are asserted here.
- Already approved imagery is skipped by the image review packet for all four
  mapped products; no repeat image approval is requested by this change.
- Local verification: 21 release-readiness/CLI tests, Ruff lint/format and diff
  checks passed. Includes freshness boundaries, combined blockers, URL omission,
  missing products and bounded output. This change does not alter storefront UI.
- Current public API `https://scentai-api-kxhe.onrender.com/api/health` returned
  `ok=true`, store `DUFYND`, 123 products. Frontend/API exact SHA parity has not
  been established in this continuation; no new deployment is claimed.
- Incremental spend: EUR 0; no paid calls, catalog activation or social writes.

Remaining work: run the existing read-only feed workflow on a revision containing
the diagnostic report, then verify current exact variants and publisher-bound
Awin clickref redirects against original sources. Source GTIN may be absent;
never substitute a historical GTIN as a current feed observation. Keep routing
disabled until independent purchase-path and applicable Owner gates pass.
