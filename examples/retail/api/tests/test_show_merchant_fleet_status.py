import json
import sys

from retail.api.show_merchant_fleet_status import main


def _write_jobs(tmp_path):
    jobs_path = tmp_path / "jobs.json"

    rows = []

    for job_id, enabled, dry_run in (
        ("ready-job", True, True),
        ("disabled-job", False, True),
        ("write-job", True, False),
    ):
        feed = tmp_path / f"{job_id}-feed.json"
        mappings = tmp_path / f"{job_id}-mappings.json"

        feed.write_text(
            '{"offers":[]}',
            encoding="utf-8",
        )
        mappings.write_text(
            '{"mappings":[]}',
            encoding="utf-8",
        )

        rows.append(
            {
                "job_id": job_id,
                "enabled": enabled,
                "config": {
                    "feed": str(feed),
                    "mappings": str(mappings),
                    "offers": str(
                        tmp_path / f"{job_id}-offers.json"
                    ),
                    "unmatched": str(
                        tmp_path / f"{job_id}-unmatched.json"
                    ),
                    "invalid": str(
                        tmp_path / f"{job_id}-invalid.json"
                    ),
                    "provider": "canonical",
                    "run_report": str(
                        tmp_path / f"{job_id}-runs.jsonl"
                    ),
                    "dry_run": dry_run,
                },
            }
        )

    jobs_path.write_text(
        json.dumps({"jobs": rows}),
        encoding="utf-8",
    )

    return jobs_path


def test_fleet_status_cli_outputs_machine_readable_json(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    jobs_path = _write_jobs(tmp_path)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "show_merchant_fleet_status",
            "--jobs",
            str(jobs_path),
            "--approvals",
            str(tmp_path / "approvals.json"),
        ],
    )

    assert main() == 0

    payload = json.loads(
        capsys.readouterr().out
    )

    assert payload["total_jobs"] == 3
    assert payload["ready"] == 1
    assert payload["disabled"] == 1
    assert payload["approval_required"] == 1


def test_fleet_status_cli_reports_attention_jobs(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    jobs_path = _write_jobs(tmp_path)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "show_merchant_fleet_status",
            "--jobs",
            str(jobs_path),
            "--approvals",
            str(tmp_path / "approvals.json"),
        ],
    )

    main()

    payload = json.loads(
        capsys.readouterr().out
    )

    assert payload["attention_required"] == 1
    assert payload["attention_job_ids"] == [
        "write-job"
    ]


def test_fleet_status_cli_handles_empty_job_list(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    jobs_path = tmp_path / "jobs.json"

    jobs_path.write_text(
        '{"jobs":[]}',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "show_merchant_fleet_status",
            "--jobs",
            str(jobs_path),
            "--approvals",
            str(tmp_path / "approvals.json"),
        ],
    )

    assert main() == 0

    payload = json.loads(
        capsys.readouterr().out
    )

    assert payload["total_jobs"] == 0
    assert payload["attention_required"] == 0
    assert payload["jobs"] == []


def test_fleet_status_cli_serializes_operator_guidance(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    jobs_path = _write_jobs(tmp_path)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "show_merchant_fleet_status",
            "--jobs",
            str(jobs_path),
            "--approvals",
            str(tmp_path / "approvals.json"),
        ],
    )

    assert main() == 0

    payload = json.loads(
        capsys.readouterr().out
    )

    assert len(payload["attention_items"]) == 1

    item = payload["attention_items"][0]

    assert item["job_id"] == "write-job"
    assert item["blocking"] is True
    assert item["reasons"] == [
        "approval_required"
    ]
    assert item["operator_actions"] == [
        "review_dry_run_and_approve"
    ]


def test_fleet_status_cli_serializes_health(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    jobs_path = _write_jobs(tmp_path)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "show_merchant_fleet_status",
            "--jobs",
            str(jobs_path),
            "--approvals",
            str(tmp_path / "approvals.json"),
        ],
    )

    assert main() == 0

    payload = json.loads(
        capsys.readouterr().out
    )

    assert payload["health_severity"] == "blocked"
    assert payload["health_blocked"] == 1
    assert payload["health_ok"] == 1
    assert payload["health_info"] == 1
    assert len(payload["health_items"]) == 3
