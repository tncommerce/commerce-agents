from datetime import UTC, datetime

from retail.api.merchant_job_approval import (
    build_job_approval,
    upsert_job_approval,
)
from retail.api.merchant_job_status_summary import (
    build_job_status_summary,
)
from retail.api.merchant_jobs import (
    MerchantJobProfile,
)
from retail.api.merchant_run_reports import (
    append_import_run_report,
    build_import_run_report,
)
from retail.api.merchant_scheduled_execution import (
    ScheduledMerchantImportConfig,
)


def _job(
    tmp_path,
    *,
    enabled=True,
    dry_run=True,
) -> MerchantJobProfile:
    feed = tmp_path / "feed.json"
    mappings = tmp_path / "mappings.json"

    feed.write_text(
        '{"offers":[]}',
        encoding="utf-8",
    )
    mappings.write_text(
        '{"mappings":[]}',
        encoding="utf-8",
    )

    config = ScheduledMerchantImportConfig(
        feed=feed,
        mappings=mappings,
        offers=tmp_path / "offers.json",
        unmatched=tmp_path / "unmatched.json",
        invalid=tmp_path / "invalid.json",
        provider="canonical",
        run_report=tmp_path / "runs.jsonl",
        dry_run=dry_run,
    )

    return MerchantJobProfile(
        job_id="notino-de",
        enabled=enabled,
        config=config,
    )


def test_disabled_job_summary_is_disabled(
    tmp_path,
) -> None:
    job = _job(
        tmp_path,
        enabled=False,
    )

    summary = build_job_status_summary(
        job,
        approvals_path=tmp_path / "approvals.json",
    )

    assert summary.job_state == "disabled"
    assert summary.enabled is False
    assert summary.latest_run_id is None


def test_ready_dry_run_summary_reports_latest_run(
    tmp_path,
) -> None:
    job = _job(tmp_path)

    report = build_import_run_report(
        provider="canonical",
        mode="DRY-RUN",
        feed_file="feed.json",
        read=10,
        new=2,
        updated=0,
        unchanged=8,
        unmatched=0,
        invalid=0,
        deactivated=0,
        occurred_at=datetime(
            2026,
            9,
            17,
            20,
            0,
            tzinfo=UTC,
        ),
        run_id="dry-run-1",
    )

    append_import_run_report(
        job.config.run_report,
        report,
    )

    summary = build_job_status_summary(
        job,
        approvals_path=tmp_path / "approvals.json",
    )

    assert summary.job_state == "ready"
    assert summary.approval_required is False
    assert summary.latest_run_id == "dry-run-1"
    assert summary.latest_run_status == "ok"
    assert summary.last_successful_write_run_id is None


def test_write_job_summary_requires_approval(
    tmp_path,
) -> None:
    job = _job(
        tmp_path,
        dry_run=False,
    )

    summary = build_job_status_summary(
        job,
        approvals_path=tmp_path / "approvals.json",
    )

    assert summary.job_state == "approval_required"
    assert summary.approval_required is True
    assert summary.approval_present is False


def test_write_job_summary_reports_last_successful_write(
    tmp_path,
) -> None:
    job = _job(
        tmp_path,
        dry_run=False,
    )

    approvals_path = tmp_path / "approvals.json"

    approval = build_job_approval(
        job_id=job.job_id,
        approved_run_id="approved-dry-run",
        config=job.config,
    )

    upsert_job_approval(
        approvals_path,
        approval,
    )

    report = build_import_run_report(
        provider="canonical",
        mode="WRITE",
        feed_file="feed.json",
        read=10,
        new=1,
        updated=1,
        unchanged=8,
        unmatched=0,
        invalid=0,
        deactivated=0,
        occurred_at=datetime(
            2026,
            9,
            17,
            21,
            0,
            tzinfo=UTC,
        ),
        run_id="write-1",
    )

    append_import_run_report(
        job.config.run_report,
        report,
    )

    summary = build_job_status_summary(
        job,
        approvals_path=approvals_path,
    )

    assert summary.job_state == "ready"
    assert summary.approval_present is True
    assert summary.latest_run_id == "write-1"
    assert summary.latest_run_status == "ok"
    assert summary.last_successful_write_run_id == "write-1"
    assert summary.last_successful_write_at is not None
