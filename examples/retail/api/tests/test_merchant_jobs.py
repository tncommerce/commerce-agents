import json

import pytest

from retail.api import merchant_jobs


def _job_payload(
    tmp_path,
    *,
    job_id="notino-de",
    enabled=False,
):
    return {
        "job_id": job_id,
        "enabled": enabled,
        "config": {
            "feed": str(tmp_path / "feed.json"),
            "mappings": str(tmp_path / "mappings.json"),
            "offers": str(tmp_path / "offers.json"),
            "unmatched": str(tmp_path / "unmatched.json"),
            "invalid": str(tmp_path / "invalid.json"),
            "provider": "canonical",
            "authoritative_merchant_id": "notino-de",
            "authoritative_data_source": "cj-feed",
            "run_report": str(tmp_path / "runs.jsonl"),
        },
    }


def test_load_and_resolve_merchant_job(tmp_path) -> None:
    path = tmp_path / "jobs.json"

    path.write_text(
        json.dumps(
            {
                "jobs": [
                    _job_payload(tmp_path)
                ]
            }
        ),
        encoding="utf-8",
    )

    jobs = merchant_jobs.load_merchant_jobs(path)
    job = merchant_jobs.get_merchant_job(
        jobs,
        "NOTINO-DE",
    )

    assert len(jobs) == 1
    assert job.job_id == "notino-de"
    assert job.enabled is False
    assert job.config.provider == "canonical"


def test_disabled_job_is_held_without_running(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "jobs.json"

    path.write_text(
        json.dumps(
            {
                "jobs": [
                    _job_payload(tmp_path)
                ]
            }
        ),
        encoding="utf-8",
    )

    jobs = merchant_jobs.load_merchant_jobs(path)

    called = False

    def fake_runner(config):
        nonlocal called
        called = True
        raise AssertionError(
            "Disabled job must not execute"
        )

    monkeypatch.setattr(
        merchant_jobs,
        "run_scheduled_import",
        fake_runner,
    )

    result = merchant_jobs.run_merchant_job(
        jobs,
        "notino-de",
    )

    assert called is False
    assert result.action == "hold"
    assert result.exit_code == 20
    assert result.reasons == ["job_disabled"]


def test_duplicate_job_ids_are_rejected(
    tmp_path,
) -> None:
    path = tmp_path / "jobs.json"

    path.write_text(
        json.dumps(
            {
                "jobs": [
                    _job_payload(
                        tmp_path,
                        job_id="notino-de",
                    ),
                    _job_payload(
                        tmp_path,
                        job_id="NOTINO-DE",
                    ),
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate merchant job_id",
    ):
        merchant_jobs.load_merchant_jobs(path)


def test_enabled_job_runs_scheduled_import(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "jobs.json"

    (tmp_path / "feed.json").write_text(
        '{"offers": []}',
        encoding="utf-8",
    )
    (tmp_path / "mappings.json").write_text(
        '{"mappings": []}',
        encoding="utf-8",
    )

    path.write_text(
        json.dumps(
            {
                "jobs": [
                    _job_payload(
                        tmp_path,
                        enabled=True,
                    )
                ]
            }
        ),
        encoding="utf-8",
    )

    jobs = merchant_jobs.load_merchant_jobs(path)

    captured = []

    def fake_runner(config):
        captured.append(config)

        return merchant_jobs.MerchantOperationalRun(
            action="continue",
            exit_code=0,
            import_exit_code=0,
            reasons=[],
            run_id="job-run-ok",
        )

    monkeypatch.setattr(
        merchant_jobs,
        "run_scheduled_import",
        fake_runner,
    )

    result = merchant_jobs.run_merchant_job(
        jobs,
        "notino-de",
    )

    assert len(captured) == 1
    assert captured[0].provider == "canonical"
    assert result.action == "continue"
    assert result.exit_code == 0
    assert result.run_id == "job-run-ok"


def test_enabled_but_unready_job_is_held(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "jobs.json"

    path.write_text(
        json.dumps(
            {
                "jobs": [
                    _job_payload(
                        tmp_path,
                        enabled=True,
                    )
                ]
            }
        ),
        encoding="utf-8",
    )

    jobs = merchant_jobs.load_merchant_jobs(path)

    called = False

    def fake_runner(config):
        nonlocal called
        called = True
        raise AssertionError(
            "Unready job must not execute"
        )

    monkeypatch.setattr(
        merchant_jobs,
        "run_scheduled_import",
        fake_runner,
    )

    result = merchant_jobs.run_merchant_job(
        jobs,
        "notino-de",
    )

    assert called is False
    assert result.action == "hold"
    assert result.exit_code == 20
    assert result.reasons == [
        "job_not_ready",
        "feed_missing",
        "mappings_missing",
    ]
