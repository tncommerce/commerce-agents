from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from .merchant_scheduled_execution import ScheduledMerchantImportConfig


class MerchantJobApproval(BaseModel):
    job_id: str
    approved_run_id: str
    approved_at: datetime
    config_fingerprint: str
    approved_feed_sha256: str
    approved_mappings_sha256: str


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def job_config_fingerprint(
    config: ScheduledMerchantImportConfig,
) -> str:
    payload = {
        "feed": str(config.feed),
        "mappings": str(config.mappings),
        "mappings_sha256": _file_sha256(config.mappings),
        "offers": str(config.offers),
        "unmatched": str(config.unmatched),
        "invalid": str(config.invalid),
        "provider": config.provider.strip().casefold(),
        "authoritative_merchant_id": config.authoritative_merchant_id,
        "authoritative_data_source": config.authoritative_data_source,
        "run_report": (
            str(config.run_report)
            if config.run_report is not None
            else None
        ),
    }

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def build_job_approval(
    *,
    job_id: str,
    approved_run_id: str,
    config: ScheduledMerchantImportConfig,
    approved_at: datetime | None = None,
) -> MerchantJobApproval:
    return MerchantJobApproval(
        job_id=job_id.strip(),
        approved_run_id=approved_run_id,
        approved_at=approved_at or datetime.now(timezone.utc),
        config_fingerprint=job_config_fingerprint(config),
        approved_feed_sha256=_file_sha256(config.feed),
        approved_mappings_sha256=_file_sha256(config.mappings),
    )


def approval_matches_job(
    approval: MerchantJobApproval,
    *,
    job_id: str,
    config: ScheduledMerchantImportConfig,
) -> bool:
    return (
        approval.job_id.strip().casefold()
        == job_id.strip().casefold()
        and approval.config_fingerprint
        == job_config_fingerprint(config)
    )


def load_job_approvals(
    path: Path,
) -> list[MerchantJobApproval]:
    if not path.exists():
        return []

    raw = json.loads(
        path.read_text(encoding="utf-8-sig")
    )

    return [
        MerchantJobApproval.model_validate(row)
        for row in raw.get("approvals", [])
    ]


def upsert_job_approval(
    path: Path,
    approval: MerchantJobApproval,
) -> None:
    approvals = load_job_approvals(path)

    by_id = {
        item.job_id.strip().casefold(): item
        for item in approvals
    }

    by_id[approval.job_id.strip().casefold()] = approval

    payload = {
        "approvals": [
            item.model_dump(mode="json")
            for item in by_id.values()
        ]
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def revoke_job_approval(
    path: Path,
    job_id: str,
) -> bool:
    approvals = load_job_approvals(path)
    key = job_id.strip().casefold()

    remaining = [
        approval
        for approval in approvals
        if approval.job_id.strip().casefold() != key
    ]

    if len(remaining) == len(approvals):
        return False

    payload = {
        "approvals": [
            approval.model_dump(mode="json")
            for approval in remaining
        ]
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return True
