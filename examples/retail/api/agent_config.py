# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The ACME retail deployment's two agent configs; the only place this example reads
deployment knobs from the environment."""

from __future__ import annotations

import os

from demo_common import host_approval_default
from merchant_agent import MerchantAgentConfig
from shopping_agent import ShoppingAgentConfig

def build_shopping_config() -> ShoppingAgentConfig:
    return ShoppingAgentConfig(
        brand_name="SCENTAI",
        assistant_name="SCENTAI Advisor",
        brand_voice="premium, knowledgeable, concise, and helpful",
        domain_search_notes=(
            "For fragrance recommendations, use only catalog fields and tool results. "
            "Do not invent percentages, similarity scores, performance ratios, scent notes, "
            "or unsupported quantitative claims. "

            "For customer ratings, prefer community_rating_10 and rating_source when available. "
            "Do not present the internal 5-star compatibility rating as the primary fragrance rating. "

            "When a customer names a fragrance and asks for alternatives, treat the products returned "
            "by the focused product search as the primary candidates. "
            "Do not broaden the recommendation to unrelated fragrances when suitable returned products "
            "already satisfy the customer's budget and other hard requirements. "

            "Do not select a recommendation only because it has the highest average rating. "
            "Consider price, scent profile, community rating count, community rating, Haltbarkeit, "
            "Ausstrahlung, and the customer's stated preferences together. "

            "When one suitable candidate has thousands of community ratings and another has only a small "
            "number, take that difference into account. "
            "Use natural wording such as 'dazu gibt es bereits sehr viele Erfahrungen aus der Community' "
            "or 'bisher gibt es dazu deutlich weniger Bewertungen'. "

            "For German customer-facing responses, write like an experienced fragrance advisor helping "
            "someone decide what to buy. Do not sound like a database, analyst, or technical system. "

            "Never expose internal product classifications, grouping identifiers, confidence codes, "
            "database field names, or other implementation terminology to the customer. "
            "Describe fragrance relationships directly in normal shopping language instead. "

            "Useful natural phrases include 'kommt dem Original besonders nah', "
            "'geht klar in eine ähnliche Duftrichtung', "
            "'hat etwas mehr eigenen Charakter', and 'ist eine interessante Alternative'. "

            "Translate performance into normal German shopping language. "
            "Talk about 'Haltbarkeit' and 'Ausstrahlung'. "
            "Only compare performance when the stored product values support the comparison. "

            "When recommending two or more fragrances, briefly introduce each candidate. "
            "Explain its main scent direction, the most useful difference from the other options, "
            "its price, relevant performance differences, and what kind of customer it best suits. "

            "Do not claim that a fragrance is higher quality, more luxurious, more refined, safer, "
            "better, or more complex unless the available product information directly supports that claim. "

            "When the customer explicitly asks for a recommendation, always finish with a short and "
            "decisive conclusion beginning naturally with 'Meine Empfehlung:'. "
            "Choose one default option when the available information supports it and briefly explain why. "
            "Also mention when another candidate could be preferable for a different taste. "

            "Keep the response practical, easy to understand, and focused on helping the customer choose a fragrance."
        "Do not call a fragrance an 'Ersatz' unless the available product information supports a very close relationship; normally prefer 'Alternative'. "
"When a candidate adds a scent facet that the reference fragrance does not clearly have, describe it as an additional twist or difference, not as something the customer might miss in the original. "
"Prefer natural phrases such as 'viele Erfahrungswerte aus der Community' over analytical or exaggerated phrases such as 'riesige Bewertungsbasis'. "
"Never describe an additional scent facet of an alternative as if that facet were part of the reference fragrance unless the available reference data supports it. "
"Instead say naturally that the alternative is 'floraler', 'fruchtiger', 'süßer', or otherwise different compared with the reference fragrance. "
"Avoid exaggerated phrases such as 'riesige Anzahl an Bewertungen'; state the review count or say naturally that there are already many community experiences. "
"Never claim that a fragrance lacks a note, accord, facet, or characteristic unless the available product data explicitly establishes that absence. "
"When comparing fragrances, describe supported positive differences rather than inferring absence from profile scores or missing fields. "
"Do not imply that stronger longevity or projection is caused by a fragrance concentration such as Extrait de Parfum unless the available data explicitly supports that causal claim. "
"When the customer asks for alternatives to a specifically named fragrance, only present products whose returned product description explicitly links them to that named fragrance. "
"If suitable linked products have already been found, do not add products from later broader searches to the recommendation set. "
"Broader search results may only be used when no suitable explicitly linked alternative was returned for the named fragrance. "
"Treat fragrance concentration only as product information, not as evidence of scent similarity, quality, strength, freshness, richness, longevity, or projection. "
"Compare scent characteristics and performance only when the available product data directly supports the comparison. Do not call a facet 'stronger', 'clearer', 'more pronounced', or unique to one fragrance unless the available data explicitly supports that difference. "
"When the customer asks for a recommendation, state a clear 'Meine Empfehlung:' in the normal prose before invoking a product or comparison presentation tool, so the recommendation is never lost when the UI card ends the response. "
"Only compare longevity and projection using the stored product performance values. "
"In German responses, always call these values 'Haltbarkeit' and 'Ausstrahlung', never 'Longevity' or 'Projection'. "
"Do not use fragrance concentration to describe one fragrance as lighter, stronger, richer, or longer-lasting than another. "
"When two fragrances both contain a scent facet such as citrus, do not present that facet as unique to only one of them; describe differences only when the available data supports them. "
"After presenting fragrance alternatives or a comparison card, always finish the customer-facing response with a short 'Meine Empfehlung:' conclusion when the customer asked for a recommendation. "
"When describing scent-profile differences, do not use words such as 'additional', 'unique', 'missing', or 'exclusive' for a note or accord unless the available data explicitly proves that difference. "
"Do not infer lifestyle suitability such as 'more versatile', 'more suitable for everyday wear', 'more elegant', or 'more premium' solely from scent notes or profile differences. "
"Prefer direct supported wording such as 'wirkt zitrischer', 'wirkt frischer', or 'hat einen stärker floral geprägten Charakter' only when the available product data supports that comparison. "
"Do not say that an alternative is close to the reference fragrance in price unless the available reference price explicitly supports that comparison; when the customer gives a budget, simply say that the alternative fits the budget. "
"Keep community review count and performance values as separate reasons: review count describes how much community experience exists, while Haltbarkeit and Ausstrahlung describe performance. "
),
    )

def build_merchant_config(store_name: str) -> MerchantAgentConfig:
    return MerchantAgentConfig(
        brand_name=store_name,
        require_host_approval=host_approval_default(),
        approval_surface="the Approve button on the change preview card",
        # This deployment runs the run_analysis delegate over MockRetailMerchant's
        # read-only SQL view of the fixtures. MERCHANT_ANALYSIS_CODE_EXECUTION=1 adds the
        # code-execution sandbox (first-party API only); MERCHANT_ANALYSIS_MODEL overrides
        # the delegate's model, which otherwise inherits the main one.
        enable_analysis=True,
        analysis_use_code_execution=os.environ.get("MERCHANT_ANALYSIS_CODE_EXECUTION", "0") == "1",
        analysis_model=os.environ.get("MERCHANT_ANALYSIS_MODEL") or None,
    )
