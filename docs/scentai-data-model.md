# SCENTAI Fragrance Data Model

Version: MVP v1

## Purpose

This schema defines the product information SCENTAI needs to recommend
fragrances based on customer preferences, budget, occasion, season,
performance and scent profile.

## Core Product Data

- product_id
- title
- brand
- price
- currency
- volume_ml
- category
- target_group
- in_stock
- image_url
- short_description

## Fragrance Profile

- fragrance_family
- top_notes
- heart_notes
- base_notes
- main_accords

## Profile Scores

All subjective profile scores use a scale from 1 to 10.

- freshness
- sweetness
- woodiness
- spiciness

1 = very low
10 = very high

## Performance Scores

- longevity
- projection

1 = very weak
10 = very strong

## Usage

- best_seasons
- occasions
- time_of_day

Possible seasons:
- spring
- summer
- autumn
- winter

Possible occasions:
- everyday
- office
- date
- evening
- formal
- leisure
- special_occasion

Possible time_of_day:
- daytime
- evening
- both

## Recommendation Data

- similar_to
- labels

These fields help SCENTAI understand relationships between fragrances
and explain recommendations.

## Commerce Data – Later Phase

These fields are prepared for monetization but are not required for the
first MVP:

- merchant
- affiliate_url
- original_price
- current_price
- price_per_ml
- availability
- last_price_update

## Data Quality Rules

SCENTAI must not invent fragrance characteristics.

Prices and availability must be treated as time-sensitive data.

Subjective scores should be based on consistent evaluation criteria.

If reliable information is unavailable, the field should remain empty
instead of being guessed.

## Example

```json
{
  "product_id": "SC-0001",
  "title": "Example Fragrance",
  "brand": "Example Brand",
  "price": 79.90,
  "currency": "EUR",
  "volume_ml": 100,
  "category": "fragrance",
  "target_group": "unisex",
  "fragrance_family": "woody-aromatic",
  "top_notes": ["bergamot"],
  "heart_notes": ["lavender"],
  "base_notes": ["cedarwood"],
  "main_accords": ["fresh", "woody", "aromatic"],
  "freshness": 8,
  "sweetness": 3,
  "woodiness": 7,
  "spiciness": 4,
  "longevity": 8,
  "projection": 7,
  "best_seasons": ["spring", "summer"],
  "occasions": ["everyday", "office"],
  "time_of_day": ["daytime"],
  "similar_to": [],
  "labels": ["fresh", "versatile"],
  "in_stock": true,
  "short_description": "Fresh and woody everyday fragrance."
}