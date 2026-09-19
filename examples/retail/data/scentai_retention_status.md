# SCENTAI Retention & Personal Value Status

Status: active
Updated: 2026-09-19

## Purpose

SCENTAI should become useful between purchase decisions, not only at the moment
someone asks for a recommendation.

The first retention layer is intentionally small, account-free and
privacy-minimized.

## Implemented MVP

### Wishlist

Path:

```text
/merkliste
```

A customer can save a fragrance from:
- fragrance detail pages
- catalog cards

Wishlist data:
- stores SCENTAI product IDs only
- lives in browser `localStorage`
- is not a customer account
- is not synchronized across devices

### Personal fragrance collection

Path:

```text
/sammlung
```

A customer can mark a fragrance as owned.

Marking a fragrance as owned automatically removes it from the wishlist so the
two states remain easy to understand.

### Collection profile

With at least two owned fragrances, SCENTAI summarizes:
- average freshness
- average sweetness
- average woodiness
- average spiciness
- number of strong representatives per profile axis (>= 7/10)
- most frequent catalog accords in the saved collection

These values describe the selected catalog products. They do not infer the
customer's personality, taste or identity.

### Optional profile-gap suggestions

If the saved collection has no fragrance rated >= 7/10 on one of the four
SCENTAI profile axes, the collection page can show one catalog fragrance with
a strong value on that axis.

Guardrails:
- framed as optional variety, never as a missing necessity
- no claim that the collection is incomplete
- no commission signal
- no merchant signal
- no hidden personal recommendation profile
- catalog popularity is used only as a tie-breaker among candidates satisfying
  the transparent profile condition

## Persistence behavior

Storage key:

```text
scentai_fragrance_library_v1
```

Schema:

```json
{
  "version": 1,
  "wishlist": ["SC-..."],
  "owned": ["SC-..."]
}
```

Safety rules:
- only valid SCENTAI product IDs are accepted
- duplicate IDs are removed
- owned products are removed from the wishlist
- each list is capped at 500 product IDs
- malformed storage falls back to an empty library
- failed storage writes must not be presented as successful

The customer can clear the personal library from the wishlist or collection
page.

## Analytics

SCENTAI records action-level events only:
- `wishlist_add`
- `wishlist_remove`
- `collection_add`
- `collection_remove`

Analytics contains:
- action type
- affected product ID
- source/surface
- anonymous hashed session context

Analytics does **not** receive:
- the complete local wishlist
- the complete local collection
- customer notes
- a personal fragrance profile
- names or email addresses

Supabase view:

```text
scentai_personal_library_engagement
```

The conversion report now includes privacy-minimized wishlist and collection
engagement. Small samples remain `early_signal`.

## Collection-aware advisor — implemented as explicit opt-in

From `/sammlung`, a customer with at least one owned fragrance can choose:

```text
Mit meiner Sammlung beraten lassen
```

The browser creates a bounded consultation handoff containing:
- owned fragrance names from the current SCENTAI catalog
- average values for the four SCENTAI profile axes
- the most frequent catalog accords
- explicit instructions not to treat ownership as proof of preference
- explicit instructions not to recommend an already-owned fragrance as a new purchase
- a request to clarify occasion, budget and desired type of addition before concrete recommendations

The handoff is customer-initiated, session-scoped, length-capped and removed from
`sessionStorage` after the advisor consumes it. Durable advisor memory remains
disabled.

The homepage also surfaces a device-local return card once wishlist or
collection items exist.

Retention reporting now includes:
- wishlist page sessions
- collection page sessions
- wishlist-add sessions
- collection-add sessions
- collection-aware advisor sessions

These are session-level product metrics, not cross-session user identity or a
true repeat-user rate.

## Not implemented yet

Deliberately deferred until usage supports the need:
- customer accounts
- cloud synchronization
- personal notes
- wear diary
- bottle size / remaining amount tracking
- ratings entered by the customer
- price alerts
- availability alerts
- collection import
- public collection sharing
- automatic or hidden advisor personalization from collection state

In particular, the advisor must not silently constrain a recommendation from
the local collection. If collection-aware recommendations are added later,
the customer should deliberately request or enable that behavior.

## Product questions to learn from real usage

After meaningful traffic exists, review:
- how many detail visitors save a fragrance
- how many wishlist products later move to owned
- which fragrances are frequently saved
- whether collection users return
- whether collection users use comparisons more often
- whether users ask for cross-device sync or notes

Do not build account infrastructure solely because it is technically possible.

## Next retention candidates

Potential next steps, ordered by dependency rather than commitment:

1. optional personal notes stored locally, if users ask for them
2. price alerts once merchant feeds are reliable enough
3. account/sync layer only if repeated usage proves cross-device demand
4. wear diary or seasonal rotation if collection engagement becomes meaningful
5. stronger collection-overlap explanations if real usage shows they help

The retention principle remains: help customers understand and enjoy fragrance
more, not create artificial pressure to buy more bottles.
