import json
from datetime import datetime, timezone

from retail.api.merchant_run_reports import (
    append_import_run_report,
    build_import_run_report,
)


def test_build_import_run_report_contains_operational_data() -> None:
    report = build_import_run_report(
        provider="canonical",
        mode="DRY-RUN",
        feed_file="notino-feed.json",
        read=100,
        new=4,
        updated=6,
        unchanged=80,
        unmatched=8,
        invalid=2,
        deactivated=1,
        authoritative_merchant_id="notino-de",
        authoritative_data_source="cj-feed",
        occurred_at=datetime(
            2026,
            9,
            17,
            18,
            0,
            tzinfo=timezone.utc,
        ),
        run_id="test-run-id",
    )

    assert report.run_id == "test-run-id"
    assert report.provider == "canonical"
    assert report.mode == "DRY-RUN"
    assert report.read == 100
    assert report.new == 4
    assert report.deactivated == 1
    assert report.authoritative_merchant_id == "notino-de"


def test_append_import_run_report_writes_jsonl(tmp_path) -> None:
    path = tmp_path / "merchant_import_runs.jsonl"

    report = build_import_run_report(
        provider="canonical",
        mode="WRITE",
        feed_file="merchant-feed.json",
        read=10,
        new=1,
        updated=2,
        unchanged=7,
        unmatched=0,
        invalid=0,
        deactivated=0,
        run_id="run-123",
    )

    append_import_run_report(path, report)

    lines = path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1

    saved = json.loads(lines[0])

    assert saved["run_id"] == "run-123"
    assert saved["mode"] == "WRITE"
    assert saved["new"] == 1
    assert saved["updated"] == 2
