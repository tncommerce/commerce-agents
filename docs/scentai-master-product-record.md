# SCENTAI Master Product Record

This document is the reference example for a fully validated SCENTAI fragrance record.

---

# Louis Vuitton Imagination

## Identity

product_id: SC-LV-IMAGINATION-100
brand: Louis Vuitton
title: Imagination
concentration: Eau de Parfum
volume_ml: 100
target_group: men
role: Benchmark
segment: luxury
release_year: 2021

## Official Product Data

official_main_notes:
- Ambroxan
- Black tea
- Bergamot

official_available_sizes_ml:
- 100
- 200

official_price_eur: 300.00
official_price_per_ml: 3.00

manufacturer_source: Louis Vuitton Germany

## Community Data

community_source: Parfumo
community_rating_10: 8.9
community_rating_count: 9481
longevity_10: 7.7
projection_10: 7.6

community_profile:
- fresh
- citrus
- aquatic
- green
- spicy

community_rank:
- #1 men's fragrances

## SCENTAI Normalized Profile

freshness: 10
sweetness: 2
woodiness: 2
spiciness: 5

profile_score_confidence: HIGH

## Score Reasoning

### Freshness: 10/10

Community profile:
- fresh = dominant signal
- citrus = major signal
- aquatic = major supporting signal
- green = supporting signal

Official support:
- bergamot

Freshness is one of the defining characteristics of the fragrance.

### Sweetness: 2/10

No strong sweet or gourmand accord dominates the community profile.

Official main notes do not include:
- vanilla
- caramel
- honey
- tonka
- praline

The fragrance is therefore classified as very low in sweetness.

### Woodiness: 2/10

Woodiness is not a defining community accord.

No prominent wood note appears among the manufacturer's main notes.

Woody character may exist in the composition, but it is not strong enough
to define the SCENTAI profile.

### Spiciness: 5/10

Spicy character appears in the community profile but is not dominant.

The fragrance therefore receives a moderate spiciness score.

## Usage Profile

best_seasons:
- spring
- summer

best_time:
- daytime
- evening

occasions:
- everyday
- office
- leisure
- special_occasion

## Market Data

market_price_method: official retail price
market_price_eur: 300.00
price_per_ml: 3.00

german_availability: LIMITED_DIRECT
availability_note:
Exclusive through Louis Vuitton online and selected Louis Vuitton stores.

price_checked_at: 2026-09-07
price_source_count: 1

## Relationships

cluster: Louis Vuitton Imagination

relationship_role: Benchmark

MVP related products:
- Arabiyat Prestige Marwa EDP
- Arabiyat Prestige Marwa Extrait
- Bujairami Hectic

Watchlist:
- Alezz Hersh 2

## Evidence Confidence

official_product_data: HIGH
community_metrics: HIGH
market_price: HIGH
profile_scores: HIGH
relationship_data: MEDIUM

overall_evidence_confidence: HIGH

## Opportunity Evidence

retail_signal:
Luxury exclusive with limited retail distribution.

community_signal:
Extremely high — currently ranked #1 among men's fragrances on Parfumo
with thousands of community ratings.

alternative_demand_signal:
HIGH — several popular fragrances are explicitly compared with or inspired
by Imagination.

price_gap_signal:
HIGH — official 100 ml price is €300, creating significant room for
lower-priced alternatives.

german_availability_signal:
MEDIUM — reliably available through the brand, but not broadly distributed
across conventional fragrance retailers.

## Validation Status

official_data_verified: YES
community_data_verified: YES
price_verified: YES
profile_scores_reviewed: YES
relationships_reviewed: YES

catalog_ready: YES