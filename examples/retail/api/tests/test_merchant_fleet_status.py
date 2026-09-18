from retail.api.merchant_fleet_status import (
    build_fleet_status_summary,
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
    job_id,
    *,
    enabled=True,
    dry_run=True,
) -> MerchantJobProfile:
    feed = tmp_path / f"{job_id}-feed.json"
    mappings = tmp_path / f"{job_id}-mappings.json"

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
        offers=tmp_path / f"{job_id}-offers.json",
        unmatched=tmp_path / f"{job_id}-unmatched.json",
        invalid=tmp_path / f"{job_id}-invalid.json",
        provider="canonical",
        run_report=tmp_path / f"{job_id}-runs.jsonl",
        dry_run=dry_run,
    )

    return MerchantJobProfile(
        job_id=job_id,
        enabled=enabled,
        config=config,
    )


def test_fleet_summary_counts_job_states(
    tmp_path,
) -> None:
    jobs = [
        _job(
            tmp_path,
            "ready-job",
        ),
        _job(
            tmp_path,
            "disabled-job",
            enabled=False,
        ),
        _job(
            tmp_path,
            "write-job",
            dry_run=False,
        ),
    ]

    fleet = build_fleet_status_summary(
        jobs,
        approvals_path=tmp_path / "approvals.json",
    )

    assert fleet.total_jobs == 3
    assert fleet.ready == 1
    assert fleet.disabled == 1
    assert fleet.not_ready == 0
    assert fleet.approval_required == 1
    assert fleet.attention_required == 1
    assert fleet.attention_job_ids == ["write-job"]


def test_review_run_marks_enabled_job_for_attention(
    tmp_path,
) -> None:
    job = _job(
        tmp_path,
        "review-job",
    )

    report = build_import_run_report(
        provider="canonical",
        mode="DRY-RUN",
        feed_file=job.config.feed.name,
        read=10,
        new=0,
        updated=0,
        unchanged=9,
        unmatched=1,
        invalid=0,
        deactivated=0,
        run_id="review-run",
    )

    append_import_run_report(
        job.config.run_report,
        report,
    )

    fleet = build_fleet_status_summary(
        [job],
        approvals_path=tmp_path / "approvals.json",
    )

    assert fleet.latest_run_review == 1
    assert fleet.attention_required == 1
    assert fleet.attention_job_ids == ["review-job"]


def test_disabled_job_does_not_require_attention(
    tmp_path,
) -> None:
    job = _job(
        tmp_path,
        "disabled-review-job",
        enabled=False,
    )

    report = build_import_run_report(
        provider="canonical",
        mode="DRY-RUN",
        feed_file=job.config.feed.name,
        read=1,
        new=0,
        updated=0,
        unchanged=0,
        unmatched=1,
        invalid=0,
        deactivated=0,
        run_id="old-review-run",
    )

    append_import_run_report(
        job.config.run_report,
        report,
    )

    fleet = build_fleet_status_summary(
        [job],
        approvals_path=tmp_path / "approvals.json",
    )

    assert fleet.disabled == 1
    assert fleet.latest_run_review == 1
    assert fleet.attention_required == 0
    assert fleet.attention_job_ids == []


def test_fleet_attention_includes_approval_guidance(
    tmp_path,
) -> None:
    job = _job(
        tmp_path,
        "approval-job",
        dry_run=False,
    )

    fleet = build_fleet_status_summary(
        [job],
        approvals_path=tmp_path / "approvals.json",
    )

    assert len(fleet.attention_items) == 1

    item = fleet.attention_items[0]

    assert item.job_id == "approval-job"
    assert item.blocking is True
    assert item.reasons == ["approval_required"]
    assert item.operator_actions == ["review_dry_run_and_approve"]


def test_fleet_attention_includes_review_guidance(
    tmp_path,
) -> None:
    job = _job(
        tmp_path,
        "review-guidance-job",
    )

    report = build_import_run_report(
        provider="canonical",
        mode="DRY-RUN",
        feed_file=job.config.feed.name,
        read=10,
        new=0,
        updated=0,
        unchanged=9,
        unmatched=1,
        invalid=0,
        deactivated=0,
        run_id="review-guidance-run",
    )

    append_import_run_report(
        job.config.run_report,
        report,
    )

    fleet = build_fleet_status_summary(
        [job],
        approvals_path=tmp_path / "approvals.json",
    )

    item = fleet.attention_items[0]

    assert item.blocking is False
    assert item.reasons == ["unmatched_rows"]
    assert item.operator_actions == ["review_unmatched_product_mappings"]


def test_fleet_health_is_blocked_when_job_is_blocked(
    tmp_path,
) -> None:
    job = _job(
        tmp_path,
        "blocked-job",
        dry_run=False,
    )

    fleet = build_fleet_status_summary(
        [job],
        approvals_path=tmp_path / "approvals.json",
    )

    assert fleet.health_severity == "blocked"
    assert fleet.health_blocked == 1
    assert fleet.health_warning == 0
    assert fleet.health_items[0].severity == "blocked"


def test_fleet_health_is_warning_for_review_run(
    tmp_path,
) -> None:
    job = _job(
        tmp_path,
        "warning-job",
    )

    report = build_import_run_report(
        provider="canonical",
        mode="DRY-RUN",
        feed_file=job.config.feed.name,
        read=5,
        new=0,
        updated=0,
        unchanged=4,
        unmatched=1,
        invalid=0,
        deactivated=0,
        run_id="warning-run",
    )

    append_import_run_report(
        job.config.run_report,
        report,
    )

    fleet = build_fleet_status_summary(
        [job],
        approvals_path=tmp_path / "approvals.json",
    )

    assert fleet.health_severity == "warning"
    assert fleet.health_warning == 1
    assert fleet.health_blocked == 0


def test_disabled_job_does_not_degrade_ready_fleet(
    tmp_path,
) -> None:
    jobs = [
        _job(
            tmp_path,
            "ready-health-job",
        ),
        _job(
            tmp_path,
            "disabled-health-job",
            enabled=False,
        ),
    ]

    fleet = build_fleet_status_summary(
        jobs,
        approvals_path=tmp_path / "approvals.json",
    )

    assert fleet.health_severity == "ok"
    assert fleet.health_ok == 1
    assert fleet.health_info == 1
