# DUFYND affiliate verification queue · 25 September 2026

This queue is the hand-off for the next authenticated Awin/CJ browser session. Repository state must not be upgraded from memory, activity-feed wording or email alone when the network's authoritative program-status screen disagrees.

## Current repository state

| Merchant | Network | Repo state | Next authoritative check |
| --- | --- | --- | --- |
| Perfumetrader | Awin | approved / active homepage tracking | Await the sent feed/image-rights follow-up; then validate feed/API and product-deeplink strategy. |
| top Parfümerie | Awin | applied / pending | Re-open the program status page. Prior activity wording indicated participation was confirmed, but the last authoritative open-program list still showed it open. |
| Douglas | Awin | applied / pending | Check current program decision. |
| flaconi | Awin | applied / pending | Check current program decision. |
| Breuninger | Awin | applied / pending | Check current program decision. |
| Birkholz | Awin | applied / pending | Check current program decision. |
| parfumdreams | Awin | rejected | No activation; keep rejection unless network status changes through a new application/decision. |
| ParfumGroup | Awin | rejected | No activation; keep rejection unless network status changes through a new application/decision. |
| Notino | CJ Affiliate | applied_pending | Check CJ status separately; do not infer it from Awin. |

## Awin session checklist

For every pending Awin advertiser:

1. open the advertiser/program status, not only the activity feed;
2. record the exact current decision and date visible in the network;
3. if approved, record advertiser ID and determine whether a homepage tracked link can be verified;
4. check whether a product feed is available and whether it exposes image URL fields;
5. record any advertiser-specific image/creative restrictions before an image is considered rights-cleared for DUFYND;
6. do not activate product offers until exact SKU mapping, deeplink/tracking, freshness and image rights all pass independently.

## Data mutation rule

After an authenticated check, update the canonical application file first:

- `examples/retail/data/scentai_affiliate_programs.json`

Then regenerate/reconcile:

- `examples/retail/data/merchant_partners.json`
- `examples/retail/data/scentai_affiliate_activation_status.json`

Approved status does not automatically mean a product-specific offer is ready. Product-level routing remains separately gated.

## Current email dependency

A follow-up to Perfumetrader asking about product data/feed and image material was sent on 25 September. No inbound reply was present at the latest mailbox check. Do not send another follow-up before a reasonable response window unless new context justifies it.
