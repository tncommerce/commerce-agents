from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .merchant_feed_reader import (
    DEFAULT_MAX_FEED_BYTES,
    DEFAULT_MAX_FEED_ROWS,
)
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
    feed_format: Literal["auto", "json", "csv"] = "auto"
    max_feed_bytes: int = DEFAULT_MAX_FEED_BYTES
    max_feed_rows: int = DEFAULT_MAX_FEED_ROWS
    authoritative_merchant_id: str | None = None
    authoritative_data_source: str | None = None
    run_report: Path | None = None
    dry_run: bool = False


def validate_schedule_config(
    config: ScheduledMerchantImportConfig,
) -> None:
    if config.max_feed_bytes < 1:
        raise ValueError("max_feed_bytes must be at least 1")

    if config.max_feed_rows < 1:
        raise ValueError("max_feed_rows must be at least 1")

    if (config.authoritative_merchant_id is None) != (config.authoritative_data_source is None):
        raise ValueError(
            "authoritative_merchant_id and authoritative_data_source must be provided together"
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
        "--feed-format",
        config.feed_format,
        "--max-feed-bytes",
        str(config.max_feed_bytes),
        "--max-feed-rows",
        str(config.max_feed_rows),
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
