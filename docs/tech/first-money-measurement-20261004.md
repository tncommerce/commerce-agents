# First-money measurement contract

Scope: 1 Million EDT 100 ml / Perfumetrader Awin and Delina EDP 75 ml / Notino CJ.
Audited base: `8fc8d777107706e70e8aa8097686e92e6f2872b7`.
No product, offer economics, visual, rights, activation or publication changes.

## First-party funnel

`src`, `cmp`, `content` become `acquisition_source`, `campaign_id`, `content_id`.
The browser stores these in sessionStorage and carries them through internal navigation.
`page_view`, `fragrance_detail_view`, `offer_section_view` and `offer_section_open`
use the active API session. Offer links carry that session as `sid`; the server hashes
it with SHA-256 and retains the first 24 hex characters as `session_key`.
The browser suite checks both products and Instagram/TikTok through landing,
catalog, detail, visible offers and the clickout link using one API session.

Merchant clickouts are recorded by the redirect endpoint, not counted again by the
browser. Their durable row contains `event_id`, `session_key`, `product_id`,
`offer_id`, `source` (merchant), `acquisition_source`, `campaign_id`, `content_id`.
The local clickout log uses the same event ID and hashed session key.
Without a valid browser session, a clickout gets a separate fallback session;
it must not be guessed into a landing session. Full reloads, different devices,
separate tabs and lost/blocked storage may split sessions; this is not cross-device tracking.

## Awin

For the current `www.awin1.com` redirect, all existing clickrefs are removed:

| Awin parameter | DUFYND value |
| --- | --- |
| clickref | content_id, otherwise campaign_id/source |
| clickref2 | campaign_id |
| clickref3 | acquisition_source |
| clickref4 | anonymous API session ID |
| clickref5 | product_id |
| clickref6 | offer_id |

The advertiser, publisher and exact destination URL are retained. An export/API
response with all six references can be joined to the hashed DUFYND session and
offer. With only the primary clickref, report content-level attribution, not an
invented session match. The historical static `one_million_example61_01` is not
a unique session key and must not be assigned to tomorrow's experiment.

## CJ

The verified current Notino route is
`www.jdoqocy.com/click-101884613-12260695?url=...`.
Previously it sent no SID. It now sends exactly one `sid`: the server-generated
clickout UUID with hyphens removed (32 opaque alphanumeric characters).
Any previous SID is replaced. PID, AID and exact merchant destination are retained.
There are no six independent CJ fields and no invented CJ `cjevent`.

When CJ returns that SID, resolve the durable row using:

```sql
select event_id, session_key, product_id, offer_id, source,
       acquisition_source, campaign_id, content_id, occurred_at
from public.scentai_analytics_events
where event = 'merchant_clickout'
  and replace(event_id::text, '-', '') = :cj_sid;
```

This gives a deterministic per-click match to all six dimensions. SID-free or
unmatched network records remain unmatched. Sending an SID is tested separately
from CJ/Notino returning it on a real commission: the latter needs real network
evidence and cannot be proven by a fabricated sale or a followed test redirect.

## Transactions and commission: owner data gate

There is no connected production network transaction ingestion in this release.
The first proof requires an owner-provided Awin transaction export and/or CJ
commission-detail export containing the references, or authorized publisher API
credentials with verified field access. No account configuration is modified.
The SID patch itself requires no external configuration or new credentials.

Retain the actual network transaction/commission ID, advertiser, event date,
references/SID, order value/currency, commission/currency, status and amendment
date. Deduplicate by network plus transaction/commission ID, using the latest
authoritative state. Keep pending, approved, reversed and paid values separate.
Do not infer the purchased SKU from the clicked SKU unless basket evidence proves it.
Clicks are not sales; revenue and commission remain unknown until network evidence.

## Tomorrow's test

On 2026-10-05 (Europe/Berlin), Instagram 10:00 and TikTok 18:00 use
`content_id=one_million_still_hits_20261004_01` and
`campaign_id=fms_1m_still_hits_20261004` when those identifiers are present in the
actual inbound URL. Social scheduling and links are not changed by this release.
Count landing sessions, detail sessions, offer-visible/open sessions and merchant
clickout sessions by campaign/content/source/product/offer. Organic or generic
bio-link traffic without these identifiers must remain separately unattributed.

QA traffic uses a `qa_` campaign/content namespace and must be excluded from real
experiment counts. No test redirect is followed to Awin, CJ or a merchant.

## Deployment

Before the API deployment, add the nullable `offer_id` column to
`public.scentai_analytics_events` (the canonical schema SQL is idempotent).
Do not alter RLS, policies, grants or existing events. Verify live redirect headers
without following redirects, then verify the corresponding QA row in Supabase.

Sources: Awin publisher Transactions API
<https://help.awin.com/apidocs/returns-a-list-of-transactions-for-a-given-publisher>;
CJ SID definition
<https://junction.cj.com/article/cj-account-manager-top-notch-tactical-tips>;
CJ Commission Detail reference
<https://developers.cj.com/graphql/reference/Commission%20Detail>.
