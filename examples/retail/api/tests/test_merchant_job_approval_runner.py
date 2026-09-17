from retail.api import merchant_job_approval_runner as approval_runner
from retail.api.merchant_jobs import MerchantJobProfile
from retail.api.merchant_operational_runner import MerchantOperationalRun
from retail.api.merchant_scheduled_execution import (
    ScheduledMerchantImportConfig,
)


def _job(tmp_path, *, dry_run=True):
    feed = tmp_path / "feed.json"
    mappings = tmp_path / "mappings.json"

    feed.write_text(
        '{"offers": []}',
        encoding="utf-8",
    )
    mappings.write_text(
        '{"mappings": []}',
        encoding="utf-8",
    )

    return MerchantJobProfile(
        job_id="notino-de",
        enabled=False,
        config=ScheduledMerchantImportConfig(
            feed=feed,
            mappings=mappings,
            offers=tmp_path / "offers.json",
            unmatched=tmp_path / "unmatched.json",
            invalid=tmp_path / "invalid.json",
            provider="canonical",
            authoritative_merchant_id="notino-de",
            authoritative_data_source="cj-feed",
            run_report=tmp_path / "runs.jsonl",
            dry_run=dry_run,
        ),
    )


def _clean_operational_result(job):
    return MerchantOperationalRun(
        action="continue",
        exit_code=0,
        import_exit_code=0,
        reasons=[],
        run_id="dry-run-123",
        payload={
            "status": "ok",
            "exit_code": 0,
            "reasons": [],
            "run": {
                "run_id": "dry-run-123",
                "occurred_at": "2026-09-17T18:00:00Z",
                "provider": job.config.provider,
                "mode": "DRY-RUN",
                "feed_file": job.config.feed.name,
                "authoritative_merchant_id":
                    job.config.authoritative_merchant_id,
                "authoritative_data_source":
                    job.config.authoritative_data_source,
                "allow_empty_authoritative": False,
                "read": 1,
                "new": 1,
                "updated": 0,
                "unchanged": 0,
                "unmatched": 0,
                "invalid": 0,
                "deactivated": 0,
            },
        },
    )


def test_clean_fresh_dry_run_creates_approval(
    tmp_path,
    monkeypatch,
) -> None:
    job = _job(tmp_path)

    monkeypatch.setattr(
        approval_runner,
        "run_scheduled_import",
        lambda config: _clean_operational_result(job),
    )

    approvals_path = tmp_path / "approvals.json"

    result = approval_runner.approve_job_from_fresh_dry_run(
        job,
        approvals_path=approvals_path,
    )

    assert result.action == "approved"
    assert result.exit_code == 0
    assert result.approved_run_id == "dry-run-123"
    assert approvals_path.exists()


def test_write_mode_cannot_be_approved(
    tmp_path,
    monkeypatch,
) -> None:
    job = _job(
        tmp_path,
        dry_run=False,
    )

    called = False

    def fake_runner(config):
        nonlocal called
        called = True
        raise AssertionError(
            "Write-mode job must not run approval dry-run"
        )

    monkeypatch.setattr(
        approval_runner,
        "run_scheduled_import",
        fake_runner,
    )

    result = approval_runner.approve_job_from_fresh_dry_run(
        job,
        approvals_path=tmp_path / "approvals.json",
    )

    assert called is False
    assert result.action == "hold"
    assert result.reasons == [
        "job_not_in_dry_run_mode"
    ]


def test_mismatched_dry_run_evidence_is_rejected(
    tmp_path,
    monkeypatch,
) -> None:
    job = _job(tmp_path)
    operational = _clean_operational_result(job)
    operational.payload["run"]["provider"] = "wrong-provider"

    monkeypatch.setattr(
        approval_runner,
        "run_scheduled_import",
        lambda config: operational,
    )

    approvals_path = tmp_path / "approvals.json"

    result = approval_runner.approve_job_from_fresh_dry_run(
        job,
        approvals_path=approvals_path,
    )

    assert result.action == "hold"
    assert result.exit_code == 20
    assert result.reasons == [
        "dry_run_evidence_mismatch"
    ]
    assert not approvals_path.exists()
