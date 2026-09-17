# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The ACME retail merchant router: the shared portal routes over ``MockRetailMerchant``,
plus the KPI trends and insight cards the retail portal's home page shows."""

from __future__ import annotations

from fastapi import APIRouter

from commerce_common.memory import MemoryStore
from demo_common import REPO_ROOT, MerchantIdentity, build_merchant_router
from merchant_agent_runtime import MerchantAgent

from .agent_config import build_merchant_config
from .merchant_fleet_status import (
    build_fleet_status_summary,
)
from .merchant_jobs import load_merchant_jobs
from .mock_merchant import MockRetailMerchant
from .mock_retail import DATA_DIR, MockRetail

IDENTITY = MerchantIdentity(merchant_id="acme-retail", operator="Avery")


def merchant_fleet_status_payload() -> dict:
    jobs = load_merchant_jobs(
        DATA_DIR / "merchant_jobs.json"
    )

    summary = build_fleet_status_summary(
        jobs,
        approvals_path=(
            DATA_DIR
            / "merchant_job_approvals.json"
        ),
    )

    return summary.model_dump(
        mode="json"
    )


def create_merchant_router(storefront: MockRetail, memory_store: MemoryStore) -> APIRouter:
    config = build_merchant_config(storefront.store_name)
    merchant = MockRetailMerchant(storefront, config, merchant_id=IDENTITY.merchant_id)
    agent = MerchantAgent(
        backend=merchant,
        skills_dir=REPO_ROOT / "merchant-agent" / "skills",
        config=config,
        memory_store=memory_store,
    )
    return build_merchant_router(
        storefront=storefront,
        backend=merchant,
        agent=agent,
        identity=IDENTITY,
        example_dir="retail",
        overview_extras=lambda: {
            "trends": merchant.kpi_trends(),
            "trends_prior": merchant.kpi_trends(periods_back=1),
            "insights": merchant.home_insights(),
        },
        portal_reads={
            "/operations/fleet-status":
                merchant_fleet_status_payload,
        },
    )
