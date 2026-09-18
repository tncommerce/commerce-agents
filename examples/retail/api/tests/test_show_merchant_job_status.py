import json
import sys

import pytest

from retail.api.show_merchant_job_status import main


def _write_jobs(
    tmp_path,
    *,
    enabled=False,
    dry_run=True,
):
    feed = tmp_path / "feed.json"
    mappings = tmp_path / "mappings.json"
    jobs = tmp_path / "jobs.json"

    feed.write_text(
        '{"offers":[]}',
        encoding="utf-8",
    )

    mappings.write_text(
        '{"mappings":[]}',
        encoding="utf-8",
    )

    jobs.write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "job_id": "notino-de",
                        "enabled": enabled,
                        "config": {
                            "feed": str(feed),
                            "mappings": str(mappings),
                            "offers": str(tmp_path / "offers.json"),
                            "unmatched": str(tmp_path / "unmatched.json"),
                            "invalid": str(tmp_path / "invalid.json"),
                            "provider": "canonical",
                            "run_report": str(tmp_path / "runs.jsonl"),
                            "dry_run": dry_run,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    return jobs


def test_status_cli_outputs_machine_readable_json(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    jobs = _write_jobs(
        tmp_path,
        enabled=True,
        dry_run=True,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "show_merchant_job_status",
            "notino-de",
            "--jobs",
            str(jobs),
            "--approvals",
            str(tmp_path / "approvals.json"),
        ],
    )

    exit_code = main()

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["job_id"] == "notino-de"
    assert payload["job_state"] == "ready"
    assert payload["dry_run"] is True


def test_status_cli_reports_disabled_job(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    jobs = _write_jobs(
        tmp_path,
        enabled=False,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "show_merchant_job_status",
            "notino-de",
            "--jobs",
            str(jobs),
            "--approvals",
            str(tmp_path / "approvals.json"),
        ],
    )

    assert main() == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["job_state"] == "disabled"
    assert payload["enabled"] is False


def test_status_cli_rejects_unknown_job(
    tmp_path,
    monkeypatch,
) -> None:
    jobs = _write_jobs(tmp_path)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "show_merchant_job_status",
            "unknown-job",
            "--jobs",
            str(jobs),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
