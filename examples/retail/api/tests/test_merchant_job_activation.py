import json

from retail.api.merchant_job_activation import (
    activate_merchant_job,
)
from retail.api.merchant_job_approval import (
    build_job_approval,
    upsert_job_approval,
)
from retail.api.merchant_jobs import (
    get_merchant_job,
    load_merchant_jobs,
)


def _write_job(tmp_path):
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

    jobs_path = tmp_path / "jobs.json"

    jobs_path.write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "job_id": "notino-de",
                        "enabled": False,
                        "config": {
                            "feed": str(feed),
                            "mappings": str(mappings),
                            "offers": str(
                                tmp_path / "offers.json"
                            ),
                            "unmatched": str(
                                tmp_path / "unmatched.json"
                            ),
                            "invalid": str(
                                tmp_path / "invalid.json"
                            ),
                            "provider": "canonical",
                            "authoritative_merchant_id":
                                "notino-de",
                            "authoritative_data_source":
                                "cj-feed",
                            "run_report": str(
                                tmp_path / "runs.jsonl"
                            ),
                            "dry_run": True,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    return jobs_path


def test_activation_requires_valid_approval(
    tmp_path,
) -> None:
    jobs_path = _write_job(tmp_path)

    result = activate_merchant_job(
        jobs_path=jobs_path,
        approvals_path=tmp_path / "approvals.json",
        job_id="notino-de",
    )

    assert result.action == "hold"
    assert result.exit_code == 20
    assert result.reasons == [
        "valid_approval_required"
    ]

    job = get_merchant_job(
        load_merchant_jobs(jobs_path),
        "notino-de",
    )

    assert job.enabled is False
    assert job.config.dry_run is True


def test_valid_approval_activates_write_mode(
    tmp_path,
) -> None:
    jobs_path = _write_job(tmp_path)
    approvals_path = tmp_path / "approvals.json"

    job = get_merchant_job(
        load_merchant_jobs(jobs_path),
        "notino-de",
    )

    approval = build_job_approval(
        job_id="notino-de",
        approved_run_id="dry-run-approved",
        config=job.config,
    )

    upsert_job_approval(
        approvals_path,
        approval,
    )

    result = activate_merchant_job(
        jobs_path=jobs_path,
        approvals_path=approvals_path,
        job_id="notino-de",
    )

    assert result.action == "activated"
    assert result.exit_code == 0

    updated = get_merchant_job(
        load_merchant_jobs(jobs_path),
        "notino-de",
    )

    assert updated.enabled is True
    assert updated.config.dry_run is False
