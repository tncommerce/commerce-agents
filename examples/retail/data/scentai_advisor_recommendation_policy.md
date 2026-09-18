# SCENTAI Advisor Recommendation Policy

Status: active
Updated: 2026-09-18

## Purpose

The SCENTAI Advisor ranks fragrances from verified catalog data and the
customer's current request. Recommendation order must be explainable from
catalog evidence and must never be influenced by affiliate commission.

## Hard constraints

Explicit customer constraints are applied before recommendation ranking.

Examples:
- maximum price
- minimum rating
- explicit category or attribute filters

A high-confidence direct name match does not bypass a hard constraint. If the
named fragrance conflicts with the supplied filter, the direct lookup returns
no qualifying result instead of silently showing the product anyway.

## Named fragrances and alternatives

Short inputs that resemble a fragrance or brand name are treated as possible
named-product lookups before generic fragrance discovery.

When a customer asks for an alternative to a named benchmark:
- use the explicit SCENTAI relationship graph first
- keep the search inside the relevant verified cluster when linked candidates
  exist
- apply budget and other hard constraints
- use relationship confidence and community evidence as ranking support
- do not add unrelated fragrances merely to fill the result count

Customer-facing relationship copy is German and avoids internal terms such as
cluster IDs or confidence codes.

## Query-intent ranking

SCENTAI uses deterministic catalog fields for the following intents.

### Summer / hot weather

Signals:
- high freshness
- lower sweetness
- fresh, citrus, aquatic and green catalog accords
- heavy gourmand profiles receive a small negative adjustment

### Winter / cold weather

Signals:
- sweetness
- woodiness
- spiciness
- warm catalog accords such as sweet, spicy, gourmand, oriental, woody and
  creamy
- longevity

### Spring

Signals:
- freshness
- moderate sweetness
- floral, fruity, green, citrus and fresh catalog accords

### Autumn

Signals:
- sweetness
- woodiness
- spiciness
- woody, spicy, sweet, fruity, smoky and oriental catalog accords
- longevity

### Office / business

Signals:
- freshness
- controlled sweetness
- controlled projection
- fresh or powdery catalog character where present

### Date / evening

Signals:
- warm profile dimensions
- longevity
- moderate-to-strong but not extreme projection

### Party / club

Signals:
- projection
- longevity
- energetic sweet/spicy profile dimensions

### Everyday

Signals:
- balanced freshness
- non-extreme sweetness
- moderate projection
- useful longevity

These are ranking signals, not universal claims about how every person should
wear a fragrance.

## Query-specific fit labels

Search results may contain the customer-facing value `anfrage_passung`.
It is derived deterministically from the same verified profile/performance
fields used for ranking.

Examples:
- frisches Sommerprofil
- geringe Süße
- ausgewogenes Büroprofil
- warmes Winterprofil
- frisches Frühlingsprofil
- warmes Herbstprofil
- starkes Abendprofil
- starke Präsenz für Party oder Club
- ausgewogenes Alltagsprofil
- starke Haltbarkeit
- starke Ausstrahlung

The field name itself is internal implementation terminology and must never be
shown in natural-language advisor prose. The value may be rendered as a
customer-facing recommendation chip.

Absence of a fit label does not prove that a fragrance is unsuitable; it only
means the deterministic threshold for that label was not met.

## Explanation guardrails

- Never infer quality, luxury or superiority from community rating alone.
- Never infer performance from concentration.
- Never claim an accord is absent merely because it is not listed among the
  main accords.
- Use Haltbarkeit and Ausstrahlung for performance in German.
- Keep recommendation explanations tied to returned catalog evidence.
- Do not expose raw scoring formulas or internal field names.
- Affiliate commission is not a ranking input.

## Advisor-to-storefront handoff

Recommendation cards support:
- full fragrance detail page
- current merchant offers
- free fragrance comparison

The comparison handoff preserves the selected fragrance through the URL.
Two-product advisor comparison cards can open the full SCENTAI comparison with
both fragrances already selected.

## Regression coverage

The recommendation acceptance suite covers:
- budget-safe named lookups
- exact named lookup without conflicting filters
- named benchmark alternatives
- fresh / low-sweetness requests
- summer intent
- winter intent
- spring intent
- autumn intent
- office intent
- party intent
- everyday intent
- longevity / projection intent
- German sharp-s normalization
- German alternative copy

Run the retail API test suite before treating recommendation-ranking changes as
production-safe.
