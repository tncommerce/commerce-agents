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
approval remain separate and false. Rows lacking explicit stock or German
shipping cost/destination remain on HOLD. No current product result is claimed
until the encrypted artifact has been retrieved and independently reviewed.

Local targeted verification covers variant and GTIN conflicts, duplicate
matches, stale/naive timestamps, missing shipping and stock, credential URL
rejection, unknown-column exclusion, authenticated recipient encryption and
raw-file cleanup on network failure. Regular PR CI remains required.
