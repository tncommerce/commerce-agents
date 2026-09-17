from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel

from .merchant_operational_runner import (
    MerchantOperationalRun,
    run_import_with_gate,
)


class ScheduledMerchantImportConfig(BaseModel):
    feed: Path
    mappings: Path
    offers: Path
    unmatched: Path
    invalid: Path
    provider: str = "canonical"
    authoritative_merchant_id: str | None = None
    authoritative_data_source: str | None = None
    run_report: Path | None = None
    dry_run: bool = False


def validate_schedule_config(
    config: ScheduledMerchantImportConfig,
) -> None:
    if (
        (config.authoritative_merchant_id is None)
        != (config.authoritative_data_source is None)
    ):
        raise ValueError(
            "authoritative_merchant_id and "
            "authoritative_data_source must be provided together"
        )


def build_scheduled_import_command(
    config: ScheduledMerchantImportConfig,
) -> list[str]:
    validate_schedule_config(config)

    command = [
        sys.executable,
        "-m",
        "retail.api.import_merchant_feed",
        "--feed",
        str(config.feed),
        "--mappings",
        str(config.mappings),
        "--offers",
        str(config.offers),
        "--unmatched",
        str(config.unmatched),
        "--invalid",
        str(config.invalid),
        "--provider",
        config.provider,
    ]

    if config.authoritative_merchant_id is not None:
        command.extend(
            [
                "--authoritative-merchant-id",
                config.authoritative_merchant_id,
                "--authoritative-data-source",
                config.authoritative_data_source,
            ]
        )

    if config.run_report is not None:
        command.extend(
            [
                "--run-report",
                str(config.run_report),
            ]
        )

    if config.dry_run:
        command.append("--dry-run")

    return command


def run_scheduled_import(
    config: ScheduledMerchantImportConfig,
) -> MerchantOperationalRun:
    command = build_scheduled_import_command(config)
    return run_import_with_gate(command)
