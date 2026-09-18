# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
from scripts.qa_scentai_staging import (
    TYPO_CASES,
    data_quality_issues,
    load_staging,
    run_qa,
)


def test_staging_data_quality_has_no_structural_issues() -> None:
    staging = load_staging()

    assert staging["product_count"] == 30
    assert data_quality_issues(staging) == []


@pytest.mark.asyncio
async def test_all_staged_products_pass_pre_live_recommendation_qa() -> None:
    result = await run_qa()

    assert result["product_count"] == 30
    assert result["checks"]["exact_name_search"]["tested"] == 30
    assert result["checks"]["typo_search"]["tested"] == len(TYPO_CASES)
    assert result["checks"]["budget_and_offer_qa"]["passed"] is None
    assert result["issues"] == []
    assert result["passed"] is True
