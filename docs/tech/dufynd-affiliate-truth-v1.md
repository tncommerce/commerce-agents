# Affiliate evidence: click references and qualified traffic

The existing first-party events are the join ledger, not a sales ledger.
For new offer clickouts, Awin `clickref4` and CJ `sid` carry the lowercase,
32-character hex form of the persisted analytics `event_id` UUID. Join with
`replace(event_id, '-', '')`, then read product, offer, campaign, content,
source and hashed session from that event. Two clicks in one session now have
distinct Awin references. Awin refs 1–3 and 5–6, publisher/advertiser IDs and
the exact merchant destination are unchanged. QA retains `qa_internal`.

Historical Awin `clickref4` is a browser session reference; do not reinterpret
it as an event UUID or assign a transaction to one of several clicks by guess.
Helper calls without a click ID preserve that legacy format. General merchant
discovery links are not product-level purchase or exact-SKU evidence.

The growth-report CLI now reads the existing service-only
`dufynd_visitor_analytics` view instead of raw analytics. It does not recreate
the QA classification. Offline input must explicitly say `traffic_class=visitor`;
missing or unclassified provenance is excluded. A supplied QA row excludes
its whole session even when that marker lies outside the report window. Offline
exports cannot establish facts about omitted rows; live SQL excludes QA sessions
across all stored history. Neither mode proves that an unmarked visitor is human.

## Network access verified on 2026-10-10

- Connected Windsor accounts: Instagram, TikTok Organic and YouTube only;
  no Awin or CJ reporting account is connected.
- No Awin/CJ credential is present in the current execution environment.
- The existing repository workflow consumes `AWIN_DATA_FEED_API_KEY` for product
  feed 91379. It does not read transactions. Do not reuse that credential as a
  transaction token or extract stored secrets.
- The only existing Awin transaction evidence file covers 2026-10-01 through
  2026-10-04. Its historical zero result is not a current revenue result.
- Current network conversions and commission remain **unknown**, not zero.
  No new credential, purchase, conversion API write or network integration is
  fabricated by this change.

One actionable owner handoff for the current measurement gap: provide the
original Awin and CJ transaction/commission CSV exports for 2026-10-01 through
the current date, all statuses, including publisher/advertiser, transaction ID,
transaction/validation date, ClickRef1–6 or SID, amount, currency and commission.
Include the report's selected date range and timezone even if it has no rows.
No passwords/tokens in chat. These exports enable a bounded read-only audit;
they do not create an automated ongoing API connection.

For any future authorized importer: require actual network evidence; distinguish
Sale from Lead/Bonus and pending/approved/declined/deleted; retain currency;
deduplicate network + publisher + transaction ID; apply revisions/reversals;
separate attributable from unmatched or QA transactions. An outbound product ID
does not prove the purchased SKU: only network basket data can establish it.

Primary API documentation:
- https://help.awin.com/apidocs/api-authentication
- https://help.awin.com/apidocs/returns-a-list-of-transactions-for-a-given-publisher
- https://developers.cj.com/authentication/overview

No database migration, new service, paid call, offer activation or social change.
