# DUFYND revenue reconciliation — clickout to network revenue

Status: path specified; network credentials not connected  
Date: 2026-10-04

## Evidence boundary

DUFYND currently measures first-party traffic through `merchant_clickout`. It does **not** have a production table or connected network feed that proves an affiliate sale or commission. Therefore no clickout may be reported as a sale and commission/revenue remain null until network evidence arrives.

For the existing Rabanne 1 Million cohort, Supabase currently contains the ordered tagged path:

- source: `youtube`
- campaign: `yt_1million_v8DlVXi-Fj8_p1`
- content: `one_million_example61_01`
- 4 landing sessions
- 4 product-detail sessions
- 3 offer-section-view sessions
- 1 offer-section-open session
- 1 merchant-clickout session

The 25% landing-to-clickout figure is an early n=4 signal, not a sale conversion rate.

## 1 Million network key

The current Perfumetrader Awin affiliate route uses:

- advertiser: `11672`
- merchant product: `16978322`
- clickref: `one_million_example61_01`
- tracked URL contains `awinaffid=3099222`

An older DUFYND rebrand runbook refers to publisher ID `309922`. That disagreement must be resolved from the authoritative Awin account before an API call; do not infer that the tracking affiliate ID and publisher API account ID are interchangeable.

## Preferred Awin read path

Awin's publisher transaction API supports `GET /publishers/{publisherId}/transactions/` for publisher transaction reporting. It requires an OAuth2 bearer access token plus a date range and can return transaction status and publisher/advertiser exchange data such as clickref/order reference.

Minimum first read after secure connection:

- date window covering the first tagged clickout through today
- advertiser/program filtered to Perfumetrader when supported
- retain transaction ID, transaction date, advertiser/merchant, clickRef, orderRef, sale amount/currency, commission/currency, commission status and validation/amendment data
- request basket/product detail only if the network actually supplies it and it is needed for product-level reconciliation

The existing repo secret `AWIN_DATA_FEED_API_KEY` is documented for Awin product-feed download. It is **not** evidence that the OAuth2 publisher Transactions API token is configured.

## Windsor option

The connected Windsor environment supports `awin` and `cj` connectors, but neither currently has an account attached.

Awin Windsor connection requires:
- `api_key` — sensitive; enter only in Windsor's secure connection form
- `advertiser_id`

CJ Windsor connection requires:
- `account_id`
- `access_token` — sensitive; enter only in Windsor's secure connection form

After connecting either network, first call connector field discovery. Do not assume field names or commission semantics before the connected schema is returned.

For 1 Million, direct Awin transaction reconciliation is the immediate priority. CJ becomes relevant for Delina/Libre after they are live.

## CJ future path

CJ's current developer platform uses personal access tokens as Bearer credentials, and its Commission Detail API is GraphQL. Once CJ is connected, use the connected schema to retrieve actual commission-detail records for the Notino publisher relationship. Do not implement a guessed GraphQL query in Business state.

## Canonical reconciliation model

`platform_content_id`
→ `src / cmp / content`
→ DUFYND anonymous `session_key`
→ `product_id`
→ `merchant_clickout` + offer/merchant
→ network transaction ID
→ click reference / network attribution
→ order value
→ commission status
→ approved/paid commission

### Transaction rules

- A network transaction ID is the deduplication key.
- Preserve pending, approved, declined and amended/corrected history.
- For KPI totals, use the latest authoritative state per network transaction; never add pending + approved versions of the same transaction.
- Keep basket/order value separate from DUFYND commission.
- Keep pending commission separate from approved commission and paid/settled commission.
- A transaction that carries the DUFYND clickref is network attribution evidence. It does not retroactively prove which first-party browser session purchased unless a network-supported identifier safely joins them.
- Do not create test orders, self-referrals or artificial clickouts for revenue evidence.

## P1 KPI formulas

- Content Views = exact platform content-ID views.
- DUFYND Sessions = unique attributed first-party sessions.
- Product Detail Views = unique attributed `fragrance_detail_view` sessions.
- Offer Opens = unique attributed `offer_section_open` sessions.
- Merchant Clickouts = unique attributed `merchant_clickout` sessions.
- Clickout Rate = merchant-clickout sessions / qualified attributed product-detail sessions.
- Network Transactions = unique real network transaction IDs matched to the chosen attribution key.
- Approved Commission = sum of latest approved transaction commission states.
- Paid Revenue = sum of latest paid/settled commission states where the network exposes settlement.
- Revenue per 1,000 qualified visits = chosen commission state / qualified product-detail sessions × 1,000.
- Revenue per Content Piece = chosen commission state matched to that content's network attribution key.

Always label the commission state used in revenue KPIs.

## Minimal owner action

For Awin, the minimum owner action is to confirm the authoritative publisher/account ID and securely connect an Awin API credential. The token/API key must be entered in the provider's secure form, never pasted into chat.

For Windsor, use the existing Windsor connection form for `awin`; after the account appears as connected, Business can immediately discover fields and pull the first real transaction report. No new subscription is required by this specification; if Windsor itself asks for a paid upgrade, stop rather than incur spend.

