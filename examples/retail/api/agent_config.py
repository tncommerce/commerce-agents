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
    domain_search_notes="For fragrance recommendations, use only catalog fields and tool results. Do not invent percentages, similarity scores, performance ratios, or unsupported quantitative claims. If a comparison is qualitative, describe it qualitatively. For fragrance customer ratings, prefer community_rating_10 and rating_source when available. Do not present the internal 5-star compatibility rating as the primary fragrance rating.",
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
