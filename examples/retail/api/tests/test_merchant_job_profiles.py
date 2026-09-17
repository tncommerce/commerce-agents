from pathlib import Path

from retail.api.merchant_jobs import (
    get_merchant_job,
    load_merchant_jobs,
)


def test_repository_notino_job_is_disabled_and_safe() -> None:
    path = Path(
        "examples/retail/data/merchant_jobs.json"
    )

    jobs = load_merchant_jobs(path)
    job = get_merchant_job(
        jobs,
        "notino-de",
    )

    assert job.enabled is False
    assert job.config.dry_run is True
    assert job.config.provider == "canonical"
    assert (
        job.config.authoritative_merchant_id
        == "notino-de"
    )
    assert (
        job.config.authoritative_data_source
        == "cj-feed"
    )


def test_repository_notino_job_cannot_run_when_enabled_but_unready(
    monkeypatch,
) -> None:
    from retail.api import merchant_jobs

    jobs = merchant_jobs.load_merchant_jobs(
        Path("examples/retail/data/merchant_jobs.json")
    )

    job = merchant_jobs.get_merchant_job(
        jobs,
        "notino-de",
    )

    enabled_job = job.model_copy(
        update={"enabled": True}
    )

    called = False

    def fake_runner(config):
        nonlocal called
        called = True
        raise AssertionError(
            "Unready Notino job must not execute"
        )

    monkeypatch.setattr(
        merchant_jobs,
        "run_scheduled_import",
        fake_runner,
    )

    result = merchant_jobs.run_merchant_job(
        [enabled_job],
        "notino-de",
    )

    assert called is False
    assert result.action == "hold"
    assert result.exit_code == 20
    assert result.reasons[0] == "job_not_ready"
    assert "feed_missing" in result.reasons
