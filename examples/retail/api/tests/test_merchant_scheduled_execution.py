import sys

import pytest

from retail.api import merchant_scheduled_execution as scheduled


def test_scheduled_config_builds_controlled_command(tmp_path) -> None:
    config = scheduled.ScheduledMerchantImportConfig(
        feed=tmp_path / "feed.json",
        mappings=tmp_path / "mappings.json",
        offers=tmp_path / "offers.json",
        unmatched=tmp_path / "unmatched.json",
        invalid=tmp_path / "invalid.json",
        provider="canonical",
        authoritative_merchant_id="notino-de",
        authoritative_data_source="cj-feed",
        run_report=tmp_path / "runs.jsonl",
    )

    command = scheduled.build_scheduled_import_command(config)

    assert command[0] == sys.executable
    assert command[1:3] == [
        "-m",
        "retail.api.import_merchant_feed",
    ]

    assert "--provider" in command
    assert "canonical" in command
    assert "--authoritative-merchant-id" in command
    assert "--authoritative-data-source" in command
    assert "--run-report" in command

    assert "--allow-empty-authoritative" not in command


def test_scheduled_config_rejects_partial_authoritative_scope(
    tmp_path,
) -> None:
    config = scheduled.ScheduledMerchantImportConfig(
        feed=tmp_path / "feed.json",
        mappings=tmp_path / "mappings.json",
        offers=tmp_path / "offers.json",
        unmatched=tmp_path / "unmatched.json",
        invalid=tmp_path / "invalid.json",
        authoritative_merchant_id="notino-de",
    )

    with pytest.raises(
        ValueError,
        match="must be provided together",
    ):
        scheduled.build_scheduled_import_command(config)


def test_scheduled_import_continues_clean_run(
    tmp_path,
    monkeypatch,
) -> None:
    config = scheduled.ScheduledMerchantImportConfig(
        feed=tmp_path / "feed.json",
        mappings=tmp_path / "mappings.json",
        offers=tmp_path / "offers.json",
        unmatched=tmp_path / "unmatched.json",
        invalid=tmp_path / "invalid.json",
        provider="canonical",
    )

    captured_command = []

    def fake_runner(command):
        captured_command.extend(command)
        return scheduled.MerchantOperationalRun(
            action="continue",
            exit_code=0,
            import_exit_code=0,
            reasons=[],
            run_id="scheduled-ok",
        )

    monkeypatch.setattr(
        scheduled,
        "run_import_with_gate",
        fake_runner,
    )

    result = scheduled.run_scheduled_import(config)

    assert result.action == "continue"
    assert result.exit_code == 0
    assert result.run_id == "scheduled-ok"
    assert "--machine-readable" not in captured_command
    assert "--allow-empty-authoritative" not in captured_command


def test_scheduled_import_holds_review_run(
    tmp_path,
    monkeypatch,
) -> None:
    config = scheduled.ScheduledMerchantImportConfig(
        feed=tmp_path / "feed.json",
        mappings=tmp_path / "mappings.json",
        offers=tmp_path / "offers.json",
        unmatched=tmp_path / "unmatched.json",
        invalid=tmp_path / "invalid.json",
        provider="canonical",
    )

    monkeypatch.setattr(
        scheduled,
        "run_import_with_gate",
        lambda command: scheduled.MerchantOperationalRun(
            action="hold",
            exit_code=10,
            import_exit_code=10,
            reasons=["unmatched_rows"],
            run_id="scheduled-review",
        ),
    )

    result = scheduled.run_scheduled_import(config)

    assert result.action == "hold"
    assert result.exit_code == 10
    assert result.reasons == ["unmatched_rows"]
    assert result.run_id == "scheduled-review"


def test_scheduled_command_carries_feed_safety_settings(
    tmp_path,
) -> None:
    config = scheduled.ScheduledMerchantImportConfig(
        feed=tmp_path / "provider-export.txt",
        mappings=tmp_path / "mappings.json",
        offers=tmp_path / "offers.json",
        unmatched=tmp_path / "unmatched.json",
        invalid=tmp_path / "invalid.json",
        provider="canonical",
        feed_format="csv",
        max_feed_bytes=123456,
        max_feed_rows=789,
    )

    command = scheduled.build_scheduled_import_command(config)

    assert command[command.index("--feed-format") + 1] == "csv"

    assert command[command.index("--max-feed-bytes") + 1] == "123456"

    assert command[command.index("--max-feed-rows") + 1] == "789"


def test_scheduled_config_rejects_invalid_feed_limits(
    tmp_path,
) -> None:
    config = scheduled.ScheduledMerchantImportConfig(
        feed=tmp_path / "feed.json",
        mappings=tmp_path / "mappings.json",
        offers=tmp_path / "offers.json",
        unmatched=tmp_path / "unmatched.json",
        invalid=tmp_path / "invalid.json",
        max_feed_rows=0,
    )

    with pytest.raises(
        ValueError,
        match="max_feed_rows",
    ):
        scheduled.build_scheduled_import_command(config)
