# Private Perfumetrader DE catalog review

The successful feed-list inventory run `41186222986` identified advertiser
`11672`, German feed `29975`. That inventory is not a product observation.

Select `inventory_task=perfumetrader_private_catalog` in the existing Awin
workflow on `scentai-mvp`. The existing Top review and inventory jobs remain
mutually excluded by their original input values. There is no schedule, push
trigger, deployment, database connection, image download or affiliate click in
this new mode.

The existing source-bound downloader revalidates only the selected advertiser
and feed-list row to obtain its official download URL; no tracking URL is
constructed. Compressed and expanded responses are bounded to 64 MiB. Raw data
exists only in a temporary directory, removed on success or failure. The report
contains all 37 public profiles, at most three candidate rows per profile, and
only allowlisted fields. Hidden profiles and arbitrary feed columns do not
leave the reader. Feed-list timestamps are kept verbatim and never become
product timestamps. Timezone-free row timestamps cannot pass freshness.

The sole artifact is X25519/HKDF/AES-GCM recipient-encrypted evidence with
one-day retention. Its dedicated public recipient is separate from the
existing Top review recipient. The corresponding private key is retained by
the authorized reviewer outside the repository. No plaintext report, raw feed,
API key or secret-bearing URL is uploaded or logged. Errors use a constant
sanitized message. Recipient possession and matching fingerprint must be
confirmed before dispatch.

Statuses distinguish exact fresh, exact incomplete, stale, mismatching,
missing and ambiguous evidence. Exact fresh does not authorize publication:
offer activation, tracking click verification, asset rights and owner visual
approval remain separate and false. Rows lacking explicit stock, explicit positive `is_for_sale`, or German
shipping cost/destination remain on HOLD. Stock availability and source purchase
eligibility are separate fields; contradictory stock, shipping and source-time
aliases never pass completeness. Unitless explicit size fields remain unverified. No current product result is claimed
until the encrypted artifact has been retrieved and independently reviewed.

Local targeted verification covers variant and GTIN conflicts, duplicate
matches, stale/naive timestamps, missing shipping and stock, credential URL
rejection, unknown-column exclusion, authenticated recipient encryption and
raw-file cleanup on network failure. Regular PR CI remains required.

## Schema proof before absence claims

Product run `41189749680` successfully exported encrypted evidence, but its
first reader did not retain HTTP type, headers or a parsed row count. Its 37
`NOT_FOUND` classifications are therefore **BLOCKED_UNVERIFIED_SCHEMA**, not
evidence that those products are unavailable. The original observation and
download hash remain unchanged. The removed temporary response cannot now be
classified as an error document merely from its small size.

The corrected mode opts into HTTP status and a fixed MIME-type enum, validates
CSV body format, delimiter, unique headers, row shape, product identity/price
headers and a positive count of real product rows before matching. HTML, XML,
JSON, ZIP, error CSVs, empty feeds, missing protocol proof and malformed rows
produce 37 blocked profiles. No match may become `NOT_FOUND` without verified
schema evidence. Missing per-product availability/shipping fields still remain
separate completeness holds.

Only recognized column names, unknown-column counts, row counts and fixed
reason codes enter the encrypted diagnostics. Arbitrary header names, response
bodies, final URLs and source secrets are never logged or exported. Existing
Top/inventory reader behavior is unchanged unless the new opt-in is requested.
Any second product run requires review of this concrete correction; it is a
new schema-verification attempt, not a blind retry or a replacement timestamp.
