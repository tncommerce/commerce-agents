# SCENTAI Conversion Analytics & Funnel

Status: active
Updated: 2026-09-18

## Purpose

This layer measures whether SCENTAI recommendations lead to deeper product
engagement and merchant clickouts without storing prompt text or personal
identity data.

It is designed for product decisions, not user profiling.

## Funnel events

The first-party event stream now includes:

- `consultation_start`
  - one advisor consultation begins in a session

- `advisor_recommendation_view`
  - a SCENTAI fragrance is rendered in an advisor recommendation component
  - includes its displayed position

- `advisor_product_open`
  - a customer opens the advisor's inline fragrance detail
  - includes the recommendation position

- `fragrance_detail_view`
  - a full fragrance detail page is viewed

- `comparison_start`
  - two fragrances are compared
  - stores the two product IDs
  - surfaces distinguish advisor, free comparison, and documented comparison

- `merchant_clickout`
  - a customer opens a merchant offer
  - stores the product, merchant identifier, and the storefront surface

Legacy `product_open` events remain readable for historical engagement reports
but new advisor/detail tracking uses the more specific event names above.

## Privacy model

SCENTAI does not store:
- prompt text
- IP addresses
- user-agent strings
- names
- email addresses
- raw account identifiers

Session IDs are transformed into short SHA-256-derived session keys before
storage. Funnel analytics use those pseudonymous keys only for aggregate
session counts and event ordering.

To keep one anonymous funnel coherent when a customer moves from the advisor
to a static fragrance or comparison page, the browser creates a separate
random analytics-session ID and keeps it in tab-scoped `sessionStorage`.
The storefront/API session token is not persisted for this purpose. The raw
analytics-session ID is sent only as transient request context; the analytics
table stores only its shortened SHA-256-derived session key.

Standalone pages may create a short-lived API session solely to submit the
first-party event. If that API session becomes invalid after a Render restart,
the client retries once with a fresh API session while keeping the separate
anonymous analytics-session continuity.

Analytics events are serialized client-side in invocation order so an
automatically opened recommendation cannot overtake its recommendation-view
event in the funnel solely because two HTTP requests raced.

The new funnel context contains only:
- product ID
- related product ID for comparisons
- fixed internal surface label
- merchant/source label
- recommendation position

## Surfaces

Current surface labels include:
- `advisor_recommendation`
- `advisor_inline_detail`
- `fragrance_detail`
- `advisor_comparison_card`
- `free_comparison`
- `documented_comparison`
- `merchant_discovery`
- `acquisition_landing`

These labels let SCENTAI distinguish where a clickout or comparison happened
without recording the user's prompt.

## Sequence-aware funnel

The Supabase funnel views are sequence-aware.

For example, a merchant clickout counts as an advisor recommendation conversion
only when:
1. a recommendation was shown in that anonymous session, and
2. the clickout happened after the recommendation event.

This prevents an earlier direct merchant click from being incorrectly credited
to a later advisor recommendation.

## Supabase views

### scentai_conversion_funnel

Cohort-level session funnel:
- consultations
- recommendation sessions
- advisor-detail opens
- full-detail views
- comparisons
- merchant clickouts
- conversion percentages

### scentai_product_funnel

Per-fragrance advisor funnel:
- recommendation impressions
- unique recommendation sessions
- advisor opens
- detail views
- comparison sessions
- clickout sessions
- advisor-open rate
- recommendation-to-clickout rate

Both products in a comparison are counted in product-level comparison
engagement.

### scentai_advisor_position_engagement

Measures recommendation-card position behavior:
- position
- impressions
- unique recommendation sessions
- opens
- open rate

This is observational. Position metrics must not be treated as proof that the
position itself caused the behavior.

### scentai_clickout_surface_summary

Shows which storefront surfaces produce merchant clickouts:
- clickouts
- unique clickout sessions
- distinct products clicked
- distinct merchants clicked

### scentai_acquisition_funnel

Measures first-party acquisition landing performance:
- landing sessions
- consultations started after the landing
- recommendation sessions
- detail views
- comparisons
- merchant clickouts
- landing-to-consultation rate
- consultation-to-recommendation rate
- landing-to-clickout rate

Current landing sources are privacy-safe identifiers such as
`duftfinder`, `parfum_alternativen` and
`parfum_geschenkberater`.

Optional channel attribution is allowlisted. Supported `src` values:
- `tiktok`
- `instagram`
- `youtube`
- `organic`
- `newsletter`
- `partner`

Arbitrary `src` values are ignored rather than copied into analytics.

The pseudonymized event table and reporting views are hosted in SCENTAI's
Supabase project. Public RLS policies are not enabled for the analytics table;
writes use the server-side secret/service-role credential.

## Internal conversion report

From a trusted environment with the SCENTAI Supabase credentials:

```powershell
python scripts/report_scentai_conversion.py
```

Machine-readable output:

```powershell
python scripts/report_scentai_conversion.py --machine-readable
```

Save a point-in-time report:

```powershell
python scripts/report_scentai_conversion.py --output examples/retail/data/scentai_conversion_snapshot.json
```

The report marks product/position samples with fewer than 10 recommendation
sessions as `early_signal` by default. This avoids treating tiny samples as
stable conversion evidence.

The threshold can be changed for analysis:

```powershell
python scripts/report_scentai_conversion.py --minimum-sample-sessions 20
```

## Decision guardrails

- Do not optimize recommendation ranking for affiliate commission.
- Do not remove a better customer-fit fragrance because another product has a
  better commercial conversion rate.
- Conversion data may improve UI, catalog coverage, explanations, and merchant
  availability workflows.
- Recommendation ranking remains grounded in customer request and verified
  fragrance data.
- Small samples are directional only.
- A clickout is not the same as a completed purchase.
- Merchant-level clickouts may lead to purchases beyond the originally viewed
  fragrance, but attribution and commission eligibility remain defined by the
  partner network and merchant program.
- SCENTAI must not describe clickout rate as sales conversion unless a future
  merchant/network source provides verified order attribution.

## Baseline

The conversion funnel begins collecting the new advisor-specific events with
the Phase 4J release. Older analytics contain page views, consultations and
some legacy product-open events, but they must not be backfilled with guessed
advisor impressions or comparisons.
