# SCENTAI Data Pipeline

Version: MVP v1

## Purpose

This document defines how fragrance data is collected, normalized,
validated and prepared for the SCENTAI catalog.

The goal is to ensure that every fragrance is evaluated using the same
rules and that SCENTAI does not rely on guessed or inconsistent data.

---

## 1. Source Hierarchy

### Tier 1 – Official Manufacturer

Use for hard product facts:

- brand
- product name
- concentration
- official fragrance notes
- available bottle sizes
- official retail price where relevant

Manufacturer information has priority for factual product specifications.

### Tier 2 – Fragrance Community Data

Primary source for:

- community rating
- number of ratings
- longevity
- sillage / projection
- community accords
- popularity signals

Preferred source for the MVP:

- Parfumo

Community data must always include the source name.

### Tier 3 – Market / Retail Data

Use for:

- current market price
- German availability
- number of reputable sellers
- price range

Preferred approach:

- reputable German fragrance retailers
- established price comparison services
- official brand stores where necessary

### Tier 4 – Community Discussion

Examples:

- Reddit
- fragrance forums
- review discussions

Use mainly for:

- clone relationships
- inspired-by relationships
- emerging trends
- direct comparison insights

Do not use individual community opinions as hard product facts.

---

## 2. Price Methodology

SCENTAI should not automatically use the absolute cheapest listing.

For normally distributed fragrances:

market_price_eur =
median of the three cheapest reputable and currently available German offers
for the same bottle size.

Exclude:

- suspicious sellers
- used products
- testers unless explicitly marked
- incorrect bottle sizes
- unavailable listings
- obvious temporary pricing errors

For exclusive fragrances with no meaningful reseller market:

use the official retail price.

Store:

- market_price_eur
- original_price_eur where useful
- volume_ml
- price_per_ml
- price_checked_at
- price_source_count

Prices are time-sensitive data.

---

## 3. Community Metrics

Store separately:

- community_rating_10
- community_rating_source
- community_rating_count
- longevity_10
- projection_10

Never convert the community rating into a different scale for customer-facing
SCENTAI recommendations.

The Anthropic 5-star rating field may remain only for technical compatibility.

---

## 4. SCENTAI Profile Scores

SCENTAI uses a 1–10 scale for:

- freshness
- sweetness
- woodiness
- spiciness

These values must not be assigned purely by intuition.

They should be derived from:

1. official fragrance notes
2. community accords
3. fragrance family
4. consistent SCENTAI scoring rules

Each normalized score should also have an evidence confidence level.

---

## 5. Evidence Confidence

Possible values:

- HIGH
- MEDIUM
- LOW

HIGH:
multiple reliable sources strongly agree.

MEDIUM:
reasonable evidence exists but the product is new or opinions vary.

LOW:
limited data, very new release, weak availability or conflicting evidence.

Trend products may enter the MVP with MEDIUM confidence if their market
potential is considered unusually strong.

---

## 6. Product Relationships

SCENTAI distinguishes between:

### Benchmark
The original or reference fragrance.

### Clone
A product intentionally designed to closely reproduce another fragrance.

### Inspired
Clearly based on the same fragrance DNA but with noticeable differences.

### Alternative
Similar style, use case or scent profile without being a direct reproduction.

Store:

- related_product_id
- relationship_type
- relationship_confidence

Possible confidence:

- HIGH
- MEDIUM
- LOW

SCENTAI must not describe an Alternative as a Clone.

---

## 7. Opportunity Score

Maximum: 100 points

### Retail Demand
Maximum: 35

Signals may include:

- retailer bestseller rankings
- broad retail presence
- current sales popularity

### Community Demand
Maximum: 20

Signals may include:

- community ranking
- rating count
- search / discussion activity

### Dupe / Alternative Demand
Maximum: 20

Measures how strongly customers appear to search for or discuss alternatives
to the benchmark fragrance.

### Price Gap
Maximum: 15

Higher potential when a popular original has a meaningful price difference
versus strong alternatives.

### German Availability
Maximum: 5

Measures how realistically the product can currently be purchased in Germany.

### Monetization Potential
Maximum: 5

Measures whether reputable merchants, affiliate opportunities or realistic
purchase paths exist.

Total:

Opportunity Score = /100

---

## 8. Quality Rules

SCENTAI must:

- never invent fragrance notes
- never invent prices
- never invent ratings
- never invent percentages of similarity
- never invent performance ratios
- distinguish facts from qualitative interpretation
- state uncertainty when evidence is limited
- preserve the source of community ratings
- treat price and availability as time-sensitive

Missing reliable data is preferable to guessed data.

---

## 9. MVP Workflow

For every fragrance:

1. Identify product and role in its cluster
2. Collect official manufacturer data
3. Collect community metrics
4. Collect German market price and availability
5. Identify relationships to benchmarks or alternatives
6. Normalize SCENTAI profile scores
7. Assign evidence confidence
8. Calculate Opportunity Score
9. Validate the complete record
10. Add the product to the SCENTAI catalog

Only validated products should enter the production catalog.
---

## 10. SCENTAI Profile Scoring Rubric

SCENTAI uses integer scores from 1 to 10 for:

- freshness
- sweetness
- woodiness
- spiciness

The scores are normalized SCENTAI values.
They are not manufacturer ratings and must not be presented as such.

### Evidence Priority

Each profile score is based on three evidence layers:

1. Community accords – primary signal
2. Official manufacturer notes – supporting signal
3. Fragrance family – supporting signal

Community accords determine the starting score.
Official notes and fragrance family may adjust it.

---

### 10.1 Base Score from Community Accords

If the relevant characteristic or a mapped accord appears among the main accords:

- dominant / #1 accord = 9
- #2 accord = 8
- #3 accord = 7
- #4 accord = 6
- #5 accord = 5
- present but weak / lower-ranked = 4
- not meaningfully present = 2

The base score may then be adjusted using official notes and fragrance family.

Final values are capped between 1 and 10 and rounded to the nearest whole number.

---

### 10.2 Freshness

Strong freshness signals include:

- fresh
- citrus
- aquatic
- marine
- ozonic
- green
- aromatic
- herbal

Supporting notes include:

- bergamot
- lemon
- lime
- grapefruit
- mandarin
- orange
- neroli
- mint
- rosemary
- lavender
- ginger
- marine notes
- green notes

Adjustment rules:

- +1 if multiple strong fresh notes are officially listed
- +0.5 if one clear fresh note is officially listed
- +0.5 if the fragrance family strongly supports freshness
- -1 if heavy gourmand, resinous or dense sweet accords clearly dominate

Interpretation:

1–2 = almost no freshness
3–4 = low freshness
5–6 = balanced
7–8 = clearly fresh
9–10 = freshness is one of the defining characteristics

---

### 10.3 Sweetness

Strong sweetness signals include:

- sweet
- gourmand
- vanilla
- caramel
- honey
- syrupy
- creamy

Supporting notes include:

- vanilla
- tonka bean
- caramel
- honey
- praline
- chocolate
- cocoa
- dates
- sweet fruits
- benzoin

Adjustment rules:

- +1 if multiple strong sweet/gourmand notes are officially listed
- +0.5 if one strong sweet note is officially listed
- +0.5 if the fragrance family is clearly gourmand or sweet
- -1 if dry citrus, green, mineral or strongly woody accords dominate

Interpretation:

1–2 = very dry / essentially unsweet
3–4 = mildly sweet
5–6 = moderate sweetness
7–8 = clearly sweet
9–10 = intensely sweet / gourmand-dominant

---

### 10.4 Woodiness

Strong woodiness signals include:

- woody
- oud
- dry woods
- smoky woods
- earthy-woody

Supporting notes include:

- cedar
- sandalwood
- oud
- vetiver
- guaiac wood
- cashmere wood
- patchouli
- oak
- birch

Adjustment rules:

- +1 if multiple prominent woody notes are officially listed
- +0.5 if one clear woody note is officially listed
- +0.5 if the fragrance family is primarily woody
- -1 if the fragrance is dominated by citrus, aquatic or gourmand accords with little woody structure

Interpretation:

1–2 = almost no woody character
3–4 = light woody background
5–6 = noticeable woody structure
7–8 = strongly woody
9–10 = woods define the fragrance

---

### 10.5 Spiciness

Strong spiciness signals include:

- spicy
- warm spicy
- fresh spicy

Supporting notes include:

- pepper
- black pepper
- pink pepper
- cardamom
- cinnamon
- ginger
- clove
- nutmeg
- saffron

Adjustment rules:

- +1 if multiple prominent spices are officially listed
- +0.5 if one strong spice note is officially listed
- +0.5 if spicy accords are central to the fragrance family
- -1 if the profile is predominantly soft, creamy, aquatic or floral with very little spice

Interpretation:

1–2 = essentially non-spicy
3–4 = mild spice
5–6 = noticeable spice
7–8 = clearly spicy
9–10 = spice is a defining characteristic

---

### 10.6 Confidence for Normalized Scores

Each SCENTAI profile score must have a confidence level:

HIGH:
community accords, official notes and fragrance family strongly agree.

MEDIUM:
the overall direction is clear but evidence is incomplete or partially conflicting.

LOW:
limited community data, very new release, unclear accord structure or significant disagreement.

Store:

- profile_score_confidence

If different dimensions have materially different confidence, dimension-level confidence may be added later.

---

### 10.7 Important Rules

SCENTAI profile scores are internal normalized values.

They must not be described as:

- official manufacturer ratings
- Parfumo ratings
- scientific measurements
- exact percentages

Example:

Correct:
"SCENTAI classifies this fragrance as highly fresh at 9/10 based on its citrus-heavy profile."

Incorrect:
"Parfumo rates the freshness 9/10."

The source evidence and the SCENTAI normalized score must remain conceptually separate.
---

## 11. SCENTAI Opportunity Score Rubric

The SCENTAI Opportunity Score measures the commercial relevance of a fragrance
for the SCENTAI catalog.

Maximum score: 100 points.

It is a prioritization tool, not a measure of fragrance quality.

---

### 11.1 Retail Demand Proxy — Maximum 35 Points

Use verified bestseller and popularity signals from reputable German retailers.

Never describe retailer rankings as exact unit sales unless actual sales data
is available.

Scoring:

35 points:
Top 10 at two or more major German fragrance retailers.

32 points:
Top 10 at one major retailer and Top 50 at another.

28 points:
Top 25 at one major retailer plus another verified bestseller signal.

24 points:
Top 50 at one major retailer or multiple credible bestseller listings.

18 points:
Broad retail visibility and clear commercial popularity, but no strong
current ranking.

12 points:
Moderate retail presence with limited demand evidence.

6 points:
Exclusive / direct-only distribution with no verified retailer bestseller
ranking.

0 points:
No meaningful retail-demand evidence.

Use the strongest current evidence available.

Preferred evidence should normally be checked across at least two sources
where distribution allows it.

---

### 11.2 Community Demand — Maximum 20 Points

Community Demand is split into:

- Community Rank: maximum 10
- Rating Volume: maximum 10

#### Community Rank

10 points = rank 1–10
9 points = rank 11–25
8 points = rank 26–50
7 points = rank 51–100
5 points = rank 101–250
3 points = rank 251–500
1 point = ranked below 500
0 points = no reliable ranking

#### Rating Volume

10 points = 5,000+ ratings
9 points = 2,500–4,999
8 points = 1,000–2,499
6 points = 500–999
4 points = 200–499
2 points = 50–199
1 point = fewer than 50
0 points = no reliable rating data

Maximum combined Community Demand = 20.

For the MVP, Parfumo is the preferred community source.

---

### 11.3 Alternative / Dupe Demand — Maximum 20 Points

This dimension measures the strength of customer interest in the relationship
between a benchmark fragrance and its alternatives.

For Benchmark fragrances:

20 points:
Very large and established alternative / clone market with several popular
comparison products.

16 points:
Strong and recurring demand for alternatives.

12 points:
Clear alternative demand, but a smaller market.

8 points:
Some credible comparison activity.

4 points:
Limited alternative interest.

0 points:
No meaningful alternative market.

For Clone / Inspired / Alternative products:

20 points:
The product itself is one of the dominant alternatives to a highly demanded
benchmark.

16 points:
Widely recognized and frequently compared with the benchmark.

12 points:
Established alternative with meaningful community demand.

8 points:
Emerging or moderately discussed alternative.

4 points:
Small or weakly validated relationship demand.

0 points:
No meaningful demand signal.

Relationship evidence should come from multiple sources whenever possible.

---

### 11.4 Price Gap — Maximum 15 Points

Price comparisons must use price per ml whenever bottle sizes differ.

For Clone / Inspired / Alternative products, calculate savings against the
validated benchmark:

savings_percent =
1 - (alternative_price_per_ml / benchmark_price_per_ml)

Scoring:

15 points = 80%+ cheaper
13 points = 70–79% cheaper
11 points = 60–69% cheaper
9 points = 50–59% cheaper
6 points = 35–49% cheaper
3 points = 20–34% cheaper
1 point = less than 20% cheaper
0 points = no meaningful saving or more expensive

For Benchmark products:

Use the price gap between the benchmark and the median price per ml of its
validated MVP alternatives.

If no validated alternatives exist, Price Gap may remain unscored until the
cluster is complete.

---

### 11.5 German Availability — Maximum 5 Points

5 points:
Available from three or more reputable German sellers.

4 points:
Available from two reputable sellers or reliably available directly from the
official brand.

3 points:
One stable reputable German purchase source.

2 points:
Mostly import-based, specialist-only or irregular availability.

1 point:
Frequently unavailable or difficult to source.

0 points:
No reliable legal purchase path for German customers.

Availability is time-sensitive.

---

### 11.6 Monetization Potential — Maximum 5 Points

5 points:
Multiple reputable merchants with realistic affiliate or commercial purchase
paths.

4 points:
At least one strong commercial / affiliate-capable purchase path.

3 points:
Reliable merchants exist, but monetization opportunities are not yet verified.

2 points:
Primarily official direct sale with limited third-party monetization potential.

1 point:
Difficult commercial access.

0 points:
No realistic monetization path.

Do not claim an affiliate relationship until it has actually been verified.

---

## 12. Opportunity Score Formula

Retail Demand Proxy        /35
Community Demand           /20
Alternative / Dupe Demand  /20
Price Gap                  /15
German Availability         /5
Monetization Potential      /5

TOTAL                      /100
---

## 13. MVP Selection Rules

Opportunity Score is a major selection signal, but it does not automatically
determine the final catalog.

### Benchmark Protection

A selected fragrance cluster should normally retain at least one Benchmark
product even if a cheaper alternative receives a higher Opportunity Score.

The benchmark is required for meaningful comparisons.

### Trend Bet Rule

A maximum of three products in the initial 30-product MVP may enter primarily
because of unusually strong early momentum despite limited historical data.

Trend Bets must be labelled explicitly.

### Evidence Rule

If two products have similar Opportunity Scores, prefer:

1. higher overall evidence confidence
2. stronger German availability
3. broader customer use case
4. stronger relationship confidence

### Catalog Diversity

Do not allow a small number of fragrance DNAs to consume the entire MVP.

The final catalog should preserve meaningful coverage of:

- budget
- designer
- premium
- niche
- ultra-luxury
- fresh
- office
- evening
- gourmand
- iris
- woody
- versatile mainstream

### Strategic Exception

A product may be included below the numerical Top 30 when it provides unique
strategic value that the higher-scoring products do not provide.

Examples:

- Luxury Halo Benchmark
- important mainstream bestseller
- unique scent-profile coverage
- strategically important Trend Bet

Any strategic exception must be documented.
---

## 14. Role-Aware Commercial Scoring

Validation testing showed that a single mandatory /100 score can unfairly
penalize highly demanded standalone fragrances that do not currently have a
validated alternative or clone market.

SCENTAI therefore separates universal market demand from cluster-specific
commercial opportunity.

### Market Demand Score

Applies to every fragrance.

Retail Demand Proxy       /35
Community Demand          /20
German Availability        /5
Monetization Potential     /5

TOTAL                      /65

This score measures the direct commercial relevance of the individual
product.

---

### Cluster Opportunity Bonus

Applies only when a meaningful benchmark / alternative relationship exists.

Alternative / Dupe Demand /20
Price Gap                  /15

TOTAL                      /35

If no validated comparison market exists, this score is recorded as:

N/A

It must NOT be recorded as zero.

---

### Commercial Opportunity Score

For products with a validated comparison cluster:

Market Demand Score        /65
Cluster Opportunity Bonus  /35

TOTAL                      /100

For standalone products:

report the Market Demand Score /65 separately.

Do not fabricate a /100 score.

---

### Example – Stronger With You Intensely

Market Demand Score:

Retail Demand Proxy: 35 / 35
Community Demand: 19 / 20
German Availability: 5 / 5
Monetization Potential: 5 / 5

TOTAL:

64 / 65

Cluster Opportunity Bonus:

N/A

Reason:

The fragrance has exceptionally strong direct retail and community demand,
but SCENTAI has not yet validated a sufficiently strong alternative cluster.

The absence of a clone must not reduce its direct market-demand score.