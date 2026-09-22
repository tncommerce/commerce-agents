# DUFYND Growth Launch Plan

Status: active
Updated: 2026-09-22

## Goal

DUFYND should grow by solving fragrance decisions well enough that people
return, recommend the product and trust its merchant handoffs.

The first growth objective is not maximum traffic. It is to learn which
customer problems produce:
- consultations
- useful recommendations
- detail-page engagement
- comparisons
- merchant clickouts
- repeatable content ideas

Revenue is a consequence of useful traffic. Affiliate commission must never
become a recommendation-ranking signal.

## Public acquisition pages

DUFYND now has three focused entry pages.

### Duftfinder

Path:

```text
/duftfinder
```

Primary intent:
- personal fragrance discovery
- signature scent
- season / office / performance questions

### Parfum alternatives

Path:

```text
/parfum-alternativen
```

Primary intent:
- original vs alternative
- inspired fragrance research
- price-sensitive comparison without pretending every alternative is a clone

### Gift advisor

Path:

```text
/parfum-geschenkberater
```

Primary intent:
- fragrance gifts
- people who do not know fragrance terminology
- budget + recipient + occasion discovery

Each page can hand the visitor into a pre-defined advisor conversation after
an explicit click. Direct query-string visits do not automatically start an AI
turn; this avoids crawler-triggered API spend.

## Organic channel attribution

Use only the allowlisted channel codes:

```text
?src=tiktok
?src=instagram
?src=youtube
?src=organic
?src=newsletter
?src=partner
```

Examples:

```text
/duftfinder?src=tiktok
/parfum-alternativen?src=instagram
/parfum-geschenkberater?src=youtube
```

Unknown source values are ignored rather than written into analytics.

The first-party acquisition funnel measures landing sessions through
consultation, recommendation and merchant clickout.

Do not judge a channel from tiny samples. The reporting layer marks samples
below 10 landing/recommendation sessions as early signals by default.

## Initial content pillars

### 1. Original vs alternative

Example hooks:
- "Du magst Imagination, willst aber weniger ausgeben?"
- "Alternative heißt nicht automatisch 1:1-Klon."
- "3 Dinge, die sich zwischen Original und Alternative wirklich unterscheiden."

Primary landing:
`/parfum-alternativen`

### 2. Situation-based recommendations

Examples:
- Sommer unter 60 €
- Büro ohne den Raum zu übernehmen
- Date-Night unter 100 €
- starke Haltbarkeit
- Signature-Duft finden

Primary landing:
`/duftfinder`

### 3. Gift decisions

Examples:
- Parfum schenken ohne den Lieblingsduft zu kennen
- Geschenk unter 50 / 100 / 150 €
- Welche Fragen du vor einem Parfumgeschenk stellen solltest

Primary landing:
`/parfum-geschenkberater`

### 4. Fragrance education

Examples:
- Haltbarkeit vs Ausstrahlung
- EDP ist nicht automatisch stärker
- Was "frisch", "holzig" oder "gourmand" praktisch bedeutet
- Warum ein Duft auf zwei Menschen unterschiedlich wirken kann

Primary CTA:
DUFYND Duftfinder or catalog.

### 5. Data-backed DUFYND decisions

After real traffic exists:
- most searched fragrance gaps
- most compared pairs
- popular advisor intents
- common no-result searches

Do not publish tiny-sample behavior as broad market truth.

## First 30-day organic test

Prepare 10-15 short-form videos before active promotion.

During the first 30 days:
- publish roughly 30-50 useful short-form pieces across TikTok, Instagram Reels
  and YouTube Shorts
- reuse the same core idea across platforms rather than creating three separate
  production systems
- test 3-5 repeatable content formats
- use the focused acquisition page that matches the video intent
- review acquisition funnel data weekly
- improve hooks and landing clarity before increasing content volume

Avoid meaningful paid acquisition until:
- the advisor funnel is stable
- merchant coverage is useful
- conversion analytics has enough first-party data to identify major leaks

## Merchant-level affiliate layer

DUFYND supports two separate monetization paths.

### Product deep links

The customer opens a current offer for a specific fragrance.

Use case:
- high purchase intent
- product-specific price / stock handoff

### Merchant-level discovery links

The customer enters a participating merchant through DUFYND and may continue
shopping beyond the fragrance that originally brought them to DUFYND.

This can create additional affiliate value where the merchant/network rules
attribute an eligible later basket to DUFYND.

Guardrails:
- the partner must have an explicit active affiliate link
- the link must be HTTPS
- it must have been re-verified within 30 days
- inactive/pending partners are never rendered
- merchant-level commission never changes product recommendations
- merchant attribution is not treated as guaranteed revenue
- only verified network transaction data may later be called a sale

Douglas and Notino are registered as pending merchant partners. Their general
partner modules remain hidden until approved affiliate links are available.

## Future product-led growth ideas

These are candidates, not current launch commitments.

### Personal fragrance wardrobe — active MVP

The current retention loop now includes:
- local wishlist
- local owned-fragrance collection
- collection profile
- optional profile-diversity suggestions
- explicit collection-aware advisor handoff
- homepage return card when local fragrance data exists

The advisor uses collection context only after an explicit customer action.
Ownership is not treated as proof of preference and the collection is not
stored as durable advisor memory.

Potential future value:
- reduce redundant purchases
- help users deliberately add a different use case
- make comparisons more relevant
- create a reason to return between purchases

### Price and availability alerts

User-selected fragrances only.

Possible value:
- return visits
- high-intent affiliate traffic

Do not build until live merchant feeds are reliable enough to make alerts
trustworthy.

### Collection gap analysis

Examples:
- no fresh warm-weather scent
- several similar sweet evening scents
- missing office-friendly option

This should explain overlap rather than encourage unnecessary buying.

### Sample / decant discovery

Potential future partnerships can reduce purchase risk before a full bottle.

Any future sample partner must remain separate from recommendation ranking.

### Community contribution

Possible later inputs:
- owned / tried
- rating
- longevity
- projection

Requires abuse prevention and clear separation between verified/catalog data
and user-submitted data.

## Rolling preproduction buffer

Starting with the 2026-09-26 soft launch, DUFYND should not operate from a
same-day content production queue.

Default operating model:
- preproduce evergreen short-form content into a 2-3 week rolling buffer
- publish roughly 3-4 core creatives per week
- adapt the same core creative for TikTok, Instagram Reels and YouTube Shorts
- keep roughly 30% of future slots flexible for trends, audience questions,
  new affiliate developments and real DUFYND search/advisor demand
- maintain at least five publish-ready core creatives after the initial launch
  whenever practical
- use existing preview assets before approving additional paid generation

The prelaunch bank already covers most of the first 30-day organic test.
The content problem is therefore finalization and learning quality, not raw
idea volume.

The launch sequence should deliberately mix:
- a recognizable fragrance comparison
- a trust/education piece
- an occasion-based Duftfinder demonstration
- a profile-based discovery piece
- a gift-advisor use case

Do not optimize only for views. The more useful signals are whether the content
creates qualified DUFYND sessions, advisor starts, comparison engagement,
saves/shares and eventually trustworthy merchant handoffs.

Price-led content remains adaptive rather than fixed evergreen inventory because
every price claim must be rechecked immediately before publication.

## Weekly operating loop after launch

1. Review acquisition source funnel.
2. Review no-result searches.
3. Review research triggers.
4. Review advisor recommendation engagement.
5. Review detail/comparison clickouts.
6. Review merchant availability and stale offers.
7. Choose one customer-experience improvement.
8. Choose the next content experiments.
9. Do not change recommendation quality to chase affiliate conversion.

## Success hierarchy

In order:

1. Customer receives useful fragrance help.
2. Customer understands why DUFYND recommended something.
3. Customer trusts the comparison and merchant handoff.
4. Customer returns or recommends DUFYND.
5. Commercial conversion grows from that trust.

This hierarchy should remain true even when DUFYND expands into additional
products or business models later.
