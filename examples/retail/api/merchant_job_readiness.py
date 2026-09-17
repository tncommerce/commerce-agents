from __future__ import annotations

from pydantic import BaseModel

from .merchant_providers import available_providers
from .merchant_scheduled_execution import ScheduledMerchantImportConfig


class MerchantJobReadiness(BaseModel):
    ready: bool
    reasons: list[str]


def evaluate_job_readiness(
    config: ScheduledMerchantImportConfig,
) -> MerchantJobReadiness:
    reasons: list[str] = []

    supported = {
        provider.casefold()
        for provider in available_providers()
    }

    if config.provider.strip().casefold() not in supported:
        reasons.append("unsupported_provider")

    if not config.feed.is_file():
        reasons.append("feed_missing")

    if not config.mappings.is_file():
        reasons.append("mappings_missing")

    if (
        (config.authoritative_merchant_id is None)
        != (config.authoritative_data_source is None)
    ):
        reasons.append("incomplete_authoritative_scope")

    return MerchantJobReadiness(
        ready=not reasons,
        reasons=reasons,
    )
