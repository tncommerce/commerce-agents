from pathlib import Path

from retail.api.merchant_job_readiness import (
    evaluate_job_readiness,
)
from retail.api.merchant_jobs import (
    get_merchant_job,
    load_merchant_jobs,
)
from retail.api.merchant_scheduled_execution import (
    ScheduledMerchantImportConfig,
)


def test_ready_job_has_no_readiness_errors(
    tmp_path,
) -> None:
    feed = tmp_path / "feed.json"
    mappings = tmp_path / "mappings.json"

    feed.write_text('{"offers": []}', encoding="utf-8")
    mappings.write_text(
        '{"mappings": []}',
        encoding="utf-8",
    )

    config = ScheduledMerchantImportConfig(
        feed=feed,
        mappings=mappings,
        offers=tmp_path / "offers.json",
        unmatched=tmp_path / "unmatched.json",
        invalid=tmp_path / "invalid.json",
        provider="canonical",
    )

    readiness = evaluate_job_readiness(config)

    assert readiness.ready is True
    assert readiness.reasons == []


def test_missing_feed_and_unknown_provider_are_not_ready(
    tmp_path,
) -> None:
    mappings = tmp_path / "mappings.json"
    mappings.write_text(
        '{"mappings": []}',
        encoding="utf-8",
    )

    config = ScheduledMerchantImportConfig(
        feed=tmp_path / "missing-feed.json",
        mappings=mappings,
        offers=tmp_path / "offers.json",
        unmatched=tmp_path / "unmatched.json",
        invalid=tmp_path / "invalid.json",
        provider="unknown-provider",
    )

    readiness = evaluate_job_readiness(config)

    assert readiness.ready is False
    assert readiness.reasons == [
        "unsupported_provider",
        "feed_missing",
    ]


def test_repository_notino_job_is_not_ready_without_real_feed() -> None:
    jobs = load_merchant_jobs(
        Path("examples/retail/data/merchant_jobs.json")
    )

    job = get_merchant_job(
        jobs,
        "notino-de",
    )

    readiness = evaluate_job_readiness(job.config)

    assert readiness.ready is False
    assert "feed_missing" in readiness.reasons
