from retail.api.merchant_job_approval import (
    approval_matches_job,
    build_job_approval,
    load_job_approvals,
    upsert_job_approval,
)
from retail.api.merchant_scheduled_execution import (
    ScheduledMerchantImportConfig,
)


def _config(tmp_path, *, dry_run=True, provider="canonical"):
    feed = tmp_path / "feed.json"
    mappings = tmp_path / "mappings.json"

    if not feed.exists():
        feed.write_text(
            '{"offers": []}',
            encoding="utf-8",
        )

    if not mappings.exists():
        mappings.write_text(
            '{"mappings": []}',
            encoding="utf-8",
        )

    return ScheduledMerchantImportConfig(
        feed=tmp_path / "feed.json",
        mappings=tmp_path / "mappings.json",
        offers=tmp_path / "offers.json",
        unmatched=tmp_path / "unmatched.json",
        invalid=tmp_path / "invalid.json",
        provider=provider,
        authoritative_merchant_id="notino-de",
        authoritative_data_source="cj-feed",
        run_report=tmp_path / "runs.jsonl",
        dry_run=dry_run,
    )


def test_approval_survives_dry_run_to_write_switch(
    tmp_path,
) -> None:
    dry_config = _config(
        tmp_path,
        dry_run=True,
    )

    approval = build_job_approval(
        job_id="notino-de",
        approved_run_id="dry-run-123",
        config=dry_config,
    )

    write_config = _config(
        tmp_path,
        dry_run=False,
    )

    assert (
        approval_matches_job(
            approval,
            job_id="notino-de",
            config=write_config,
        )
        is True
    )


def test_relevant_config_change_invalidates_approval(
    tmp_path,
) -> None:
    approval = build_job_approval(
        job_id="notino-de",
        approved_run_id="dry-run-123",
        config=_config(tmp_path),
    )

    changed_config = _config(
        tmp_path,
        provider="different-provider",
    )

    assert (
        approval_matches_job(
            approval,
            job_id="notino-de",
            config=changed_config,
        )
        is False
    )


def test_job_approval_can_be_persisted_and_replaced(
    tmp_path,
) -> None:
    path = tmp_path / "approvals.json"
    config = _config(tmp_path)

    first = build_job_approval(
        job_id="notino-de",
        approved_run_id="run-1",
        config=config,
    )

    second = build_job_approval(
        job_id="notino-de",
        approved_run_id="run-2",
        config=config,
    )

    upsert_job_approval(path, first)
    upsert_job_approval(path, second)

    saved = load_job_approvals(path)

    assert len(saved) == 1
    assert saved[0].approved_run_id == "run-2"


def test_feed_change_keeps_activation_approval_valid(
    tmp_path,
) -> None:
    config = _config(tmp_path)

    approval = build_job_approval(
        job_id="notino-de",
        approved_run_id="dry-run-feed",
        config=config,
    )

    approved_snapshot = approval.approved_feed_sha256

    config.feed.write_text(
        '{"offers": [{"offer_id": "changed"}]}',
        encoding="utf-8",
    )

    assert (
        approval_matches_job(
            approval,
            job_id="notino-de",
            config=config,
        )
        is True
    )

    assert approval.approved_feed_sha256 == approved_snapshot


def test_mapping_change_invalidates_existing_approval(
    tmp_path,
) -> None:
    config = _config(tmp_path)

    approval = build_job_approval(
        job_id="notino-de",
        approved_run_id="dry-run-mapping",
        config=config,
    )

    config.mappings.write_text(
        '{"mappings": [{"product_id": "changed"}]}',
        encoding="utf-8",
    )

    assert (
        approval_matches_job(
            approval,
            job_id="notino-de",
            config=config,
        )
        is False
    )


def test_ingestion_safety_change_invalidates_approval(
    tmp_path,
) -> None:
    config = _config(tmp_path)

    approval = build_job_approval(
        job_id="notino-de",
        approved_run_id="dry-run-safety",
        config=config,
    )

    changed = config.model_copy(update={"max_feed_rows": config.max_feed_rows + 1})

    assert (
        approval_matches_job(
            approval,
            job_id="notino-de",
            config=changed,
        )
        is False
    )
