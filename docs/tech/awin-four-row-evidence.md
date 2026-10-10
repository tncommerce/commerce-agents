# Restricted four-row Awin evidence

The existing Awin workflow downloads feed 91379 in its authorized runner. The
bounded exporter selects exactly one row for each merchant product ID 780879,
825869, 787670 and 856448. Missing or duplicate rows fail closed. It reuses the
existing feed reader and its byte/row limits; no new API or credentials are added.

Only explicitly allowed source fields are retained. Missing columns, empty values
and withheld values are distinguished. No GTIN, availability or freshness value is
invented. Unknown URL hosts, paths, query keys, duplicate parameters, userinfo,
fragments, non-HTTPS URLs and unsafe nested destinations are rejected in full.
The configured feed secret is also checked before encryption. Withheld values
are never exported as hashes, encodings or encrypted data.

This repository is public. Ordinary Actions artifact download permissions do not
provide confidentiality here. Therefore the only new uploaded file is a
recipient-encrypted envelope, retained for **one day**. Encryption is X25519,
HKDF-SHA256 and AES-256-GCM using the already pinned cryptography dependency.
The ephemeral sender key, salt and nonce are fresh for every envelope; protocol
context and both public keys bind the key derivation. Plaintext is held in memory
only. No feed content or URLs are printed. Even parser errors are replaced by a
constant failure code.

`.github/dufynd-awin-evidence-recipient.pub` contains only a public X25519 key.
The private recipient key must stay outside GitHub and outside the repository.
The evidence operator retains it locally for the short-lived review; it is never
sent to the runner or saved as a GitHub secret. A reviewed public-recipient
rotation merged to `scentai-mvp` triggers this same workflow, without modifying
`main`. This narrow push trigger exists because this workflow is absent from
the default branch, so its manual dispatch UI is unavailable. Ordinary application
commits do not trigger the feed download. Existing manual execution remains.

To inspect the artifact, download only the encrypted artifact with authorized
Actions access and decrypt locally with the corresponding private key. The
envelope contains base64 `ephemeral_public`, `salt`, `nonce`, and `ciphertext`.
Derive the 32-byte key with X25519 and HKDF as in `encrypt_report`, then verify
and decrypt using AESGCM with the same `AAD`. The test suite demonstrates the
round trip and verifies rejection of a wrong recipient or tampering. Do not
publish plaintext in logs, commits, comments or Supabase. Persist only bounded
findings and artifact/run references. Remove temporary review material and the
private key after the review, or let a later review use a new recipient.

This evidence is not an approval. The existing 72-hour row-freshness check,
missing-stock default, per-asset rights/visual approvals, exact landing variant
check, publisher/clickref verification and separate Owner activation gate remain
unchanged. Feed-download freshness is not row freshness.
