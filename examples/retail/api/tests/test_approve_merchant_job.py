import json
import sys

from retail.api import approve_merchant_job


def test_approval_cli_requires_explicit_confirmation(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "approve_merchant_job",
            "notino-de",
        ],
    )

    exit_code = approve_merchant_job.main()

    payload = json.loads(
        capsys.readouterr().out
    )

    assert exit_code == 20
    assert payload["action"] == "hold"
    assert payload["reasons"] == [
        "explicit_human_confirmation_required"
    ]


def test_approval_cli_runs_confirmed_approval(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    jobs_path = tmp_path / "jobs.json"
    approvals_path = tmp_path / "approvals.json"

    jobs_path.write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "job_id": "notino-de",
                        "enabled": False,
                        "config": {
                            "feed": str(
                                tmp_path / "feed.json"
                            ),
                            "mappings": str(
                                tmp_path / "mappings.json"
                            ),
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
                            "dry_run": True,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    def fake_approval(job, *, approvals_path):
        return approve_merchant_job.MerchantJobApprovalResult(
            action="approved",
            exit_code=0,
            reasons=[],
            approved_run_id="dry-run-123",
        )

    monkeypatch.setattr(
        approve_merchant_job,
        "approve_job_from_fresh_dry_run",
        fake_approval,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "approve_merchant_job",
            "notino-de",
            "--jobs",
            str(jobs_path),
            "--approvals",
            str(approvals_path),
            "--confirm-human-approval",
        ],
    )

    exit_code = approve_merchant_job.main()

    payload = json.loads(
        capsys.readouterr().out
    )

    assert exit_code == 0
    assert payload["action"] == "approved"
    assert payload["approved_run_id"] == "dry-run-123"
