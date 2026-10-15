# Offline network reconciliation — implemented 12 October 2026

This completes the missing executable part of the 4 October revenue specification.
No network login, database migration, merchant click, offer change or public release
is involved. Original Awin/CJ exports are still absent: actual sales and commissions
remain **UNKNOWN**. The older 1–4 October owner-observed zero is not extrapolated.

## Run with an authorized original

Keep the untouched CSV, manifest and projected server event extract **outside any
git checkout**. The command refuses original inputs within git, including symlink
resolutions. It prints aggregates to stdout and writes nothing. Do not commit raw
exports, manifests containing private paths, or event/session identifiers.

```sh
python -m scripts.dufynd_network_reconciliation --manifest /private/reconciliation/manifest.json
# Optional, inside the existing growth report (offline event projection):
python -m scripts.report_dufynd_profitable_growth \
  --input /private/reconciliation/growth-events.json \
  --end 2026-10-12T08:00:00Z \
  --network-manifest /private/reconciliation/manifest.json
```

Existing growth cohort calculations stay unchanged. The optional
`network_reconciliation` section has its own source windows, status and currency
buckets. It never overwrites click-cohort revenue fields: complete transaction-date
exports do not establish complete lifetime conversion coverage for a click cohort.

No schema is guessed before the real header is available. This **illustrative**
manifest uses artificial IDs and sample column names. The operator maps exact
original headers and documented status/type values after inspecting the export;
CSV bytes are never rewritten. Owner authorization is required, but a manifest is
an attestation, not cryptographic authentication of a network sale.

```json
{
  "version": 1,
  "owner_authorized": true,
  "evidence_kind": "owner_authorized_original",
  "reports": [{
    "file": "original.csv",
    "sha256": "REPLACE_WITH_SHA256_OF_UNMODIFIED_ORIGINAL",
    "network": "awin",
    "publisher_id": "900001",
    "advertiser_ids": ["900002"],
    "as_of": "2026-10-12T08:00:00Z",
    "window_start": "2026-10-01T00:00:00Z",
    "window_end": "2026-10-12T08:00:00Z",
    "date_basis": "transaction",
    "all_statuses": true,
    "complete": true,
    "row_granularity": "transaction_totals",
    "delimiter": ",",
    "decimal_mark": ".",
    "date_format": "iso8601",
    "columns": {
      "transaction_id": "Transaction ID",
      "publisher_id": "Publisher ID",
      "advertiser_id": "Advertiser ID",
      "transaction_date": "Transaction Date",
      "sale_amount": "Sale Amount",
      "sale_currency": "Sale Currency",
      "commission": "Commission",
      "commission_currency": "Commission Currency",
      "status": "Status",
      "transaction_type": "Type",
      "clickref4": "ClickRef4",
      "product_id": "ClickRef5",
      "offer_id": "ClickRef6"
    },
    "status_map": {"pending":"pending", "approved":"approved", "declined":"declined", "reversed":"reversed"},
    "type_map": {"sale":"sale", "bonus":"other"}
  }],
  "events": {
    "file": "events.json",
    "sha256": "REPLACE_WITH_SHA256_OF_VERIFIED_SERVER_PROJECTION",
    "server_export_verified": true
  },
  "routes": [{
    "network": "awin",
    "publisher_id": "900001",
    "advertiser_id": "900002",
    "merchant_id": "merchant-synthetic",
    "product_id": "product-synthetic",
    "offer_id": "offer-synthetic",
    "event_reference_valid_from": "2026-10-10T12:00:00Z",
    "event_reference_valid_until": "2026-10-12T08:00:00Z",
    "proof_reference": "replace-with-verified-rollout-proof"
  }]
}
```

If publisher ID is absent in an account-scoped original, omit that column only
with `publisher_scope_verified: true` and a verified account identity in the
manifest. This must be checked against the actual export context, not inferred
from the merchant link. Advertiser ID is required in every row. Network can also
be mapped from a CSV field and is checked against the report scope.

Optional clickref4/SID fields may be absent: transactions then remain unmatched,
not guessed. Missing required financial/identity fields reject the entire import.
UTF-8/BOM, comma/semicolon/tab delimiters and an explicit decimal mark are supported.
For posting-date exports use `date_basis: "posting"` and additionally map
`posting_date`; both transaction chronology and posting-window membership are validated.
Thousands separators and formula-like money fields are refused. Non-ISO dates need
an explicit `date_format` (Python strptime) and `timezone` (IANA); ambiguous or
nonexistent local times are rejected. Monetary values use Decimal, never floats.
Bound: 20 files, 20 MB per source, 50,000 total rows; no implicit pagination.

## Event proof and legacy references

The projected event JSON is `{"source":"scentai_analytics_events","events":[...]}`.
Project only event_id, occurred_at, session_key, event, product_id, source, offer_id,
traffic_class, acquisition_source, campaign_id, content_id, surface and
`session_internal_qa`. The last field must be derived from **all** records of that
session, not just the selected reporting window. If that classification is absent,
matched traffic remains unknown. QA markers anywhere in the supplied session
also override a visitor label. No search terms, IPs or customer data are needed.

Only exact UUID/UUID-hex clickref4 (Awin) or SID (CJ) can match a persisted
`merchant_clickout` event. The match additionally requires a proven route with the
same network, publisher, advertiser, merchant, offer, product and event-reference
rollout interval, and a click time no later than the transaction. A matching UUID
alone is insufficient. Conflicting event IDs/routes are unmatched. Old content
references or session references are never joined to sessions, guessed, or promoted
to the event-ID format. Missing or conflicting ClickRef5/6 cannot override event
identity. No guessed top-Parfümerie URL parameters or route approvals are added.

For the existing Perfumetrader route, reuse the October 10 event-ID rollout proof
in `ops.first_money_affiliate_truth_20261010` and the latest verified interval;
do not assert that earlier session references used the new contract. A matched
click proves attribution to a click product, **not** the product finally purchased
in a merchant basket. Visitor-classified traffic is not independent human proof.

## Financial lifecycle

- Awin: deduplicate by network + publisher + advertiser + transaction ID. A newer
  report `as_of` replaces the older status/amount; input order never wins. Identical
  reimports do not add sales. Conflicts at the same timestamp or changed identity
  are quarantined. Missing later rows are not interpreted as cancellation.
- CJ: map transaction_id to **commissionId**, original_action_id to
  **originalActionId**, original to the original/correction flag, and sid to SID.
  Require `row_granularity: "commission_totals"`, not per-item amounts. Distinct
  correction IDs are signed delta totals and are netted with their one original
  action. Reimported corrections are deduplicated. Full cancellation becomes
  reversed; partial negative corrections reduce totals. An orphan correction,
  conflicting currencies/status/attribution, multiple originals or negative net
  balance quarantines the whole action. Positive correction deltas are currently
  unsupported and fail closed; do not relabel or discard them to pass validation.
- For CJ native action statuses, an explicitly reviewed mapping can use new and
  extended → pending, locked and closed → approved. Closed is **not paid**.
- Pending, approved, declined and reversed remain separate, cross-tabulated with
  internal QA, visitor-classified, unknown origin and unmatched transactions.
  Sale/order value and publisher commission are separate currencies/amounts.
  Bonus/lead/click records use transaction_type=other, never a sale claim.
- No FX conversion, estimated commission, merged-currency revenue total or payment
  inference. Approved commission is reported only in approved buckets. Paid
  commission stays null without separate settlement evidence.
- Quarantines produce PARTIAL_RECONCILIATION_HOLD. No input reports produces UNKNOWN
  with null transaction/status metrics. A valid empty complete report supports zero
  observed transactions **only in its explicit advertiser/window scope**. Missing
  later updates and reporting coverage outside that scope remain unknown.

Original CSV authenticity, account context, completeness and column semantics
remain review responsibilities. The importer cannot establish these merely from a
hash. Synthetic fixtures carry SYNTHETIC_TEST_ONLY and must never be revenue proof.

## Live observation carried into this phase

Read-only observation at 08:41 UTC / 10:41 Berlin: Metricool returned the existing
Instagram Torwart post PUBLISHED (10:00) and TikTok PENDING (18:00). No posts changed.
The website event table contains no new events since 08:00 UTC; latest event remains
11 October 19:28:15.985478 UTC. No website success is attributed to today's post.

For **1 October through this observation**, existing clickouts comprise 16 internal
QA, 6 unclassified and 1 visitor-classified. This broader window differs from the
previous report beginning 5 October (13/4/1); it is not new traffic. Of these, one
QA event and one visitor-classified event are Perfumetrader exact-offer candidates
after the verified event-ID rollout. No network report exists to join either one.
The visitor event may still be the October 11 owner test. Real matched network
transactions and commissions are UNKNOWN, not zero.

Rabanne 1 Million EDT 100 ml / GTIN 3349666007921 / Perfumetrader SKU 16978322 remains
commerce-ready on the inherited evidence: EUR 71.90 + EUR 4.99 DE shipping,
merchant-declared stock, approved publisher 3099222 / advertiser 11672. No merchant
recheck or evidence timestamp refresh was performed. Full revenue-measurement
proof and public release remain HOLD. All top photo/tracking/landing gates and
Althaïr's packaging rejection remain unchanged.

## One owner action

Provide the **original Awin CSV export** from publisher 3099222, Perfumetrader
advertiser 11672, 1–12 October 2026, all statuses, together with its shown reporting
period/timezone and export time. Include available ClickRef1–6, transaction ID/date,
sale amount/currency, commission/currency, status and type. Do not edit the CSV or
paste credentials. An empty export is useful when its filters are known. If the
export omits ClickRef4, network totals may be observed but event-level attribution
will remain unmatched. This does not require a test purchase or another clickout.

## Primary documentation checked

- Awin publisher transaction report/export: https://success.awin.com/articles/en_US/Knowledge/Publisher-Transaction-Report
- CJ correction deltas and action status: https://docs.cj.com/docs/commission-detail-api
- CJ commissionId/originalActionId field semantics: https://docs.cj.com/docs/parameters

These sources establish network semantics, not access to DUFYND's private reports.
