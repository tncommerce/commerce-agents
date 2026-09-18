from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .merchant_job_approval import (
    approval_matches_job,
    load_job_approvals,
)
from .merchant_job_readiness import (
    evaluate_job_readiness,
)
from .merchant_jobs import MerchantJobProfile
from .merchant_run_reports import (
    MerchantImportRunReport,
)
from .merchant_run_status import (
    evaluate_import_run,
)

DEFAULT_APPROVALS_PATH = Path("examples/retail/data/merchant_job_approvals.json")


class MerchantJobStatusSummary(BaseModel):
    job_id: str
    enabled: bool
    job_state: Literal[
        "disabled",
        "not_ready",
        "approval_required",
        "ready",
    ]

    provider: str
    feed_file: str
    dry_run: bool

    readiness_reasons: list[str]

    approval_required: bool
    approval_present: bool

    latest_run_id: str | None = None
    latest_run_at: datetime | None = None
    latest_run_mode: str | None = None
    latest_run_status: (
        Literal[
            "ok",
            "review",
        ]
        | None
    ) = None
    latest_run_reasons: list[str] = []

    latest_feed_sha256: str | None = None
    latest_mappings_sha256: str | None = None

    last_successful_write_run_id: str | None = None
    last_successful_write_at: datetime | None = None


def load_import_run_reports(
    path: Path,
) -> list[MerchantImportRunReport]:
    if not path.exists():
        return []

    reports: list[MerchantImportRunReport] = []

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            payload = json.loads(line)
            reports.append(MerchantImportRunReport.model_validate(payload))
        except Exception as exc:
            raise ValueError(f"Invalid merchant import run report at line {line_number}") from exc

    return reports


def _report_matches_job(
    report: MerchantImportRunReport,
    job: MerchantJobProfile,
) -> bool:
    config = job.config

    return (
        report.provider.strip().casefold() == config.provider.strip().casefold()
        and Path(report.feed_file).name == config.feed.name
        and report.authoritative_merchant_id == config.authoritative_merchant_id
        and report.authoritative_data_source == config.authoritative_data_source
    )


def _job_run_report_path(
    job: MerchantJobProfile,
) -> Path:
    if job.config.run_report is not None:
        return job.config.run_report

    return job.config.offers.with_name(".merchant_import_runs.jsonl")


def build_job_status_summary(
    job: MerchantJobProfile,
    *,
    approvals_path: Path = DEFAULT_APPROVALS_PATH,
) -> MerchantJobStatusSummary:
    readiness = evaluate_job_readiness(job.config)

    approval_required = not job.config.dry_run

    approvals = load_job_approvals(approvals_path)

    approval_present = any(
        approval_matches_job(
            approval,
            job_id=job.job_id,
            config=job.config,
        )
        for approval in approvals
    )

    if not job.enabled:
        job_state = "disabled"
    elif not readiness.ready:
        job_state = "not_ready"
    elif approval_required and not approval_present:
        job_state = "approval_required"
    else:
        job_state = "ready"

    reports = [
        report
        for report in load_import_run_reports(_job_run_report_path(job))
        if _report_matches_job(
            report,
            job,
        )
    ]

    reports.sort(key=lambda report: report.occurred_at)

    latest = reports[-1] if reports else None

    latest_status = evaluate_import_run(latest) if latest is not None else None

    successful_writes = [
        report
        for report in reports
        if report.mode.strip().upper() == "WRITE" and evaluate_import_run(report).status == "ok"
    ]

    last_successful_write = successful_writes[-1] if successful_writes else None

    return MerchantJobStatusSummary(
        job_id=job.job_id,
        enabled=job.enabled,
        job_state=job_state,
        provider=job.config.provider,
        feed_file=str(job.config.feed),
        dry_run=job.config.dry_run,
        readiness_reasons=readiness.reasons,
        approval_required=approval_required,
        approval_present=approval_present,
        latest_run_id=(latest.run_id if latest is not None else None),
        latest_run_at=(latest.occurred_at if latest is not None else None),
        latest_run_mode=(latest.mode if latest is not None else None),
        latest_run_status=(latest_status.status if latest_status is not None else None),
        latest_run_reasons=(latest_status.reasons if latest_status is not None else []),
        latest_feed_sha256=(latest.feed_sha256 if latest is not None else None),
        latest_mappings_sha256=(latest.mappings_sha256 if latest is not None else None),
        last_successful_write_run_id=(
            last_successful_write.run_id if last_successful_write is not None else None
        ),
        last_successful_write_at=(
            last_successful_write.occurred_at if last_successful_write is not None else None
        ),
    )
