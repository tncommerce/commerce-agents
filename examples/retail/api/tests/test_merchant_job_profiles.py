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
