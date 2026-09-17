from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel


class MerchantImportRunReport(BaseModel):
    run_id: str
    occurred_at: datetime
    provider: str
    mode: str
    feed_file: str
    feed_sha256: str | None = None
    mappings_sha256: str | None = None
    authoritative_merchant_id: str | None = None
    authoritative_data_source: str | None = None
    allow_empty_authoritative: bool = False
    read: int
    new: int
    updated: int
    unchanged: int
    unmatched: int
    invalid: int
    deactivated: int


def build_import_run_report(
    *,
    provider: str,
    mode: str,
    feed_file: str,
    read: int,
    feed_sha256: str | None = None,
    mappings_sha256: str | None = None,
    new: int,
    updated: int,
    unchanged: int,
    unmatched: int,
    invalid: int,
    deactivated: int,
    authoritative_merchant_id: str | None = None,
    authoritative_data_source: str | None = None,
    allow_empty_authoritative: bool = False,
    occurred_at: datetime | None = None,
    run_id: str | None = None,
) -> MerchantImportRunReport:
    return MerchantImportRunReport(
        run_id=run_id or str(uuid4()),
        occurred_at=occurred_at or datetime.now(timezone.utc),
        provider=provider,
        mode=mode,
        feed_file=feed_file,
        feed_sha256=feed_sha256,
        mappings_sha256=mappings_sha256,
        authoritative_merchant_id=authoritative_merchant_id,
        authoritative_data_source=authoritative_data_source,
        allow_empty_authoritative=allow_empty_authoritative,
        read=read,
        new=new,
        updated=updated,
        unchanged=unchanged,
        unmatched=unmatched,
        invalid=invalid,
        deactivated=deactivated,
    )


def append_import_run_report(
    path: Path,
    report: MerchantImportRunReport,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                report.model_dump(mode="json"),
                ensure_ascii=False,
            )
            + "\n"
        )
