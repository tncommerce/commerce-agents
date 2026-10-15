# PRIVACY-25: preserve both real DUFYND redirect routes

15 October 2026. Development-only correction on existing PR #793.
Source parent: `5386c7bb0e8b55147b63ca129f3cdb8a2fa6ea02`.

## Actual failure

CI 38708989223 failed four merchant-discovery browser assertions:
merchant-discovery-session-correlation, merchant-discovery-session-failure-fallback,
merchant-partner-timeout-recovery, storefront-session-request-timeout.

The original new destination guard recognized product-offer redirects at
`/api/clickout/<offer>` but missed the existing merchant-level redirect generated
by `merchantPartnerClickoutUrl` in lib/api.ts:
`/api/merchant-partners/<merchant>/clickout`.
The link was still navigable, but the helper did not append campaign/session
context. This was a genuine regression in the newly added guard, not a reason to
remove the browser assertions or to permit arbitrary API/external destinations.

## Correction and proof

Permit only the two exact redirect path shapes on the existing configured API
origin (or same-origin API), validating one decoded identifier segment. Preserve
origin, protocol, credentials, invalid path and side-effect checks. No new
merchant, redirect target, product data, price, UI or protected branch changed.

Actual local execution: `node scripts/test-attribution-boundary.mjs` with the
actual TypeScript source compiled into an isolated VM: **193 cases PASS**.
The expanded suite run against the unchanged parent analytics source fails on the
first valid merchant-level redirect with missing `src`. Both actual source copies
were checked against Git blob hashes before modification.

Source blob: `f508188b94968f51bb9ea2cbf2eefe1d2e816f97`.
Test blob: `311c9ac2556f8051f7398580d36d92b357cad278`.

The 105 existing cases remain; 88 added cases cover merchant-level links at both
origins, different API path roots, present/missing sessions, blocked storage,
QA flags, impostor origins, wrong ports/protocols, malformed paths and encodings.
Tests make zero network calls and preserve advisor session ownership.
Existing independent browser assertions remain unchanged and must still pass on
the new commit. A local PASS is not the full CI result or a production release.

## Owner-authorized external action

The owner approved the scoped actions and asked to proceed autonomously. The
previous 0 EUR additional-cost limit and evidence-based release safeguards remain.
One product-specific rights request was sent in the existing Perfumetrader email
thread and verified with a SENT readback. Private mail receipts remain in Gmail;
no private message body is copied into this public repository.

Request: exact Rabanne/Paco Rabanne 1 Million EDT 100 ml, GTIN 3349666007921,
preferably bottle only; original image plus written free website-use permission,
hosting/resizing/attribution/duration and merchant-comparison placement conditions.
No purchase, paid license acceptance, social rights use or further contacts.
The reply is still awaited: sending an inquiry does not grant image rights.

## Next cohesive implementation, not activated by this document

Continue the existing privacy workstream after this guard's regression is resolved.
Do not start another visual redesign or duplicate tracker.

- Optional measurement defaults to off; affirmative choice enables it.
- A persistent, equally easy preference/withdrawal entry is required; choosing
  no optional analytics must not block search, product pages, saved products,
  offers or the ability to reach a merchant.
- Withdrawal must invalidate queued event work, abort outstanding analytics
  requests where possible, prevent late session callbacks restoring identifiers,
  clear only relevant optional storage, and remove already decorated identifiers
  from affected links/URLs without deleting the user's fragrance collection.
- Cover client and server redirect logging consistently. Do not claim that
  disabling frontend POSTs alone prevents server-side clickout measurement.
- Preserve separate functional advisor session ownership and the existing
  destination guard. Synthetic QA markers must not become a public consent bypass.
- Tests must exercise default/allow/deny/withdraw/reload/blocked storage/multiple
  tabs, late callbacks and merchant navigation, not only a standalone preference UI.
- Retention durations, deletion jobs and provider agreements need explicit
  purpose-bound evidence. Do not invent production retention or delete live data.

Public reference checked: Section 25 TDDDG
https://www.gesetze-im-internet.juris.de/ttdsg/__25.html
and EU online privacy guidance
https://europa.eu/youreurope/business/growing/digitalising/online-privacy/indexamp_en.htm
These support conservative consent/withdrawal design but do not replace a legal
assessment of the actual deployed processing and agreements.

No deployment, migration, scheduled deletion, new Nightshift, paid call or
additional publishing is performed by this change. Existing green WOW24 reference
fa2081692e10764af619b085febca077b18f494f remains intact.
