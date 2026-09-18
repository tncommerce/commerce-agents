# SCENTAI Demand Reporting

Status: active
Updated: 2026-09-18

## Purpose

SCENTAI uses first-party, privacy-minimized analytics to decide which
catalog gaps deserve research and promotion next. Demand reporting must not
be used to collect prompt text, IP addresses, user-agent strings, email
addresses, customer names or other unnecessary personal information.

## Tracked catalog signals

- `catalog_search`: normalized catalog search with a non-zero result count
- `catalog_no_results`: normalized catalog search with zero results
- `product_open`: fragrance detail open
- `merchant_clickout`: customer follows a merchant offer

Catalog search analytics store only:
- normalized search term, maximum 80 characters
- result count
- pseudonymous hashed session key
- event timestamp
- event source

Email-like input and long phone/number-like input are discarded both in the
browser and on the API.

## Supabase views

`scentai_catalog_search_demand`
- search term
- successful search events
- no-result events
- unique sessions
- average result count
- latest search timestamp

`scentai_product_engagement`
- product opens
- merchant clickouts
- unique opening sessions
- unique clickout sessions
- latest engagement timestamp

The base analytics table keeps RLS enabled and exposes no public policies.
Production writes use the server-side Supabase secret/service-role key.

## Internal report

Run from a trusted environment that already has the SCENTAI Supabase
credentials:

```powershell
python scripts/report_scentai_demand.py
```

Optional JSON output:

```powershell
python scripts/report_scentai_demand.py --machine-readable
```

Save a point-in-time snapshot:

```powershell
python scripts/report_scentai_demand.py --output examples/retail/data/scentai_demand_snapshot.json
```

The report shows:
- top searches
- top no-result searches
- weak catalog coverage
- top product opens
- top merchant clickouts

## How demand affects catalog expansion

Demand is an input, not an automatic promotion trigger.

A missing or frequently requested fragrance may be moved higher in the
candidate-research queue, but it still has to pass the normal SCENTAI
pipeline:

Demand signal -> identity verification -> fragrance metadata -> merchant
mapping -> approved image -> current tracked affiliate offer -> staging QA ->
promotion gates -> live catalog.

Affiliate commission never affects demand ranking, fragrance recommendation
ranking or merchant-offer ordering.

## Current baseline

Search-demand tracking starts with the 4G analytics release. Historical
analytics recorded before that release do not contain catalog search terms.
This is expected and must not be backfilled with guessed data.
