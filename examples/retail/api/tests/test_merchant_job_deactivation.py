import json

from retail.api.merchant_job_approval import (
    build_job_approval,
    load_job_approvals,
    upsert_job_approval,
)
from retail.api.merchant_job_deactivation import (
    deactivate_merchant_job,
)
from retail.api.merchant_jobs import (
    get_merchant_job,
    load_merchant_jobs,
)


def _active_job(tmp_path):
    feed = tmp_path / "feed.json"
    mappings = tmp_path / "mappings.json"

    feed.write_text('{"offers": []}', encoding="utf-8")
    mappings.write_text('{"mappings": []}', encoding="utf-8")

    jobs_path = tmp_path / "jobs.json"

    jobs_path.write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "job_id": "notino-de",
                        "enabled": True,
                        "config": {
                            "feed": str(feed),
                            "mappings": str(mappings),
                            "offers": str(tmp_path / "offers.json"),
                            "unmatched": str(tmp_path / "unmatched.json"),
                            "invalid": str(tmp_path / "invalid.json"),
                            "provider": "canonical",
                            "authoritative_merchant_id": "notino-de",
                            "authoritative_data_source": "cj-feed",
                            "run_report": str(tmp_path / "runs.jsonl"),
                            "dry_run": False,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    return jobs_path


def test_deactivation_returns_job_to_safe_mode(
    tmp_path,
) -> None:
    jobs_path = _active_job(tmp_path)

    result = deactivate_merchant_job(
        jobs_path=jobs_path,
        approvals_path=tmp_path / "approvals.json",
        job_id="notino-de",
    )

    job = get_merchant_job(
        load_merchant_jobs(jobs_path),
        "notino-de",
    )

    assert result.action == "deactivated"
    assert result.exit_code == 0
    assert job.enabled is False
    assert job.config.dry_run is True


def test_deactivation_revokes_existing_approval(
    tmp_path,
) -> None:
    jobs_path = _active_job(tmp_path)
    approvals_path = tmp_path / "approvals.json"

    job = get_merchant_job(
        load_merchant_jobs(jobs_path),
        "notino-de",
    )

    approval = build_job_approval(
        job_id="notino-de",
        approved_run_id="approved-run",
        config=job.config,
    )

    upsert_job_approval(
        approvals_path,
        approval,
    )

    result = deactivate_merchant_job(
        jobs_path=jobs_path,
        approvals_path=approvals_path,
        job_id="notino-de",
    )

    assert result.approval_revoked is True
    assert load_job_approvals(approvals_path) == []
