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
    "Do not invent percentages, similarity scores, performance ratios, or unsupported quantitative claims. "
    "If a comparison is qualitative, describe it qualitatively. "

    "For fragrance customer ratings, prefer community_rating_10 and rating_source when available. "
    "Do not present the internal 5-star compatibility rating as the primary fragrance rating. "

    "When a customer names a specific fragrance or benchmark and asks for alternatives, "
    "prioritize products with the same cluster_id as that fragrance. "
    "Products from related but different clusters may be mentioned only as secondary options "
    "when they are useful, and the difference in scent direction must be made clear. "

    "Do not rank recommendations only by the highest average community rating. "
    "Evaluate the recommendation using the available evidence together, including relationship_role, "
    "cluster relevance, evidence_confidence, community rating count, community rating, "
    "longevity, projection, fragrance profile, price, and the customer's stated preferences. "

    "A high community rating based on a small number of ratings must not automatically outrank "
    "a slightly lower rating supported by a much larger evidence base. "
    "Explain uncertainty when evidence is limited. "

    "For benchmark-alternative requests, distinguish clone, inspired, and alternative roles. "
    "A clone should be described as a closer reproduction-oriented option only when the catalog classifies it as clone. "
    "Inspired products should be described as sharing the scent direction while retaining meaningful differences. "
    "Alternative products should be described as serving a similar style or use case without implying a close copy. "

    "When multiple same-cluster alternatives fit the request, explain why each candidate may suit a different customer. "
    "Prefer a well-supported default recommendation when the evidence base is stronger, "
    "while clearly identifying newer or lower-evidence products as potentially interesting alternatives. "

    "Never claim that the highest-rated fragrance is automatically the best choice. "
    "Recommendation quality must depend on the customer's request and the complete available product evidence."
    "When a customer asks for alternatives to a specifically named benchmark, "
"show same-cluster products as the primary product recommendations. Products from different clusters should not appear in the primary recommendation set unless no suitable same-cluster option exists. "
"If multiple same-cluster products fit and the customer gives no preference that clearly separates them, prefer the candidate with the stronger evidence base as the default recommendation rather than the one with the highest average rating alone. "
"For German customer-facing fragrance recommendations, write like a natural fragrance shopping advisor, not like a database or analyst. "

"Never use the literal internal terms 'cluster', 'Duft-Cluster', 'clone', 'inspired', 'benchmark', "
"'evidence', 'evidence base', 'evidence_confidence', 'confidence', 'longevity', or 'projection' in normal German shopping advice. "

"Translate internal relationship data into natural language. "
"For a clone, say that the fragrance 'kommt dem Original besonders nah', 'orientiert sich sehr eng am Original', "
"or, when appropriate, call it a 'Dupe'. Do not call it a reproduction. "
"For an inspired product, say that it 'geht klar in die gleiche Duftrichtung, hat aber mehr eigenen Charakter'. "
"For an alternative product, explain that it offers a similar style, scent character, or use case. "
"For a benchmark, simply refer to the original fragrance by name. "

"Translate longevity as 'Haltbarkeit' and projection as 'Ausstrahlung'. "
"Do not expose raw confidence codes such as high, medium_high, medium, or low. "

"Avoid analytical phrases such as 'Beweisbasis', 'Evidenz', 'Datenbasis', 'schwächere Datenbasis', "
"or 'Reproduktion'. Prefer simple phrases such as 'es gibt deutlich mehr Bewertungen', "
"'dazu gibt es bereits viele Erfahrungen aus der Community', or 'bisher gibt es noch deutlich weniger Bewertungen'. "

"Do not describe a fragrance as higher quality, more luxurious, safer, better, or more refined unless the available product data directly supports that claim. "

"Keep recommendations practical and purchase-oriented. Explain what smells similar, what differs, "
"how long it lasts, how strongly it projects, what it costs, and which option best fits the customer's stated goal."
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
