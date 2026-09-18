import json
import sys

from retail.api import deactivate_merchant_job


def test_deactivation_cli_requires_explicit_confirmation(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "deactivate_merchant_job",
            "notino-de",
        ],
    )

    exit_code = deactivate_merchant_job.main()

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 20
    assert payload["action"] == "hold"
    assert payload["reasons"] == ["explicit_human_deactivation_required"]
    assert payload["approval_revoked"] is False


def test_confirmed_deactivation_calls_service(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    jobs_path = tmp_path / "jobs.json"
    approvals_path = tmp_path / "approvals.json"

    called = {}

    def fake_deactivation(
        *,
        jobs_path,
        approvals_path,
        job_id,
    ):
        called["jobs_path"] = jobs_path
        called["approvals_path"] = approvals_path
        called["job_id"] = job_id

        return deactivate_merchant_job.MerchantJobDeactivationResult(
            action="deactivated",
            exit_code=0,
            reasons=[],
            job_id=job_id,
            approval_revoked=True,
        )

    monkeypatch.setattr(
        deactivate_merchant_job,
        "deactivate_merchant_job",
        fake_deactivation,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "deactivate_merchant_job",
            "notino-de",
            "--jobs",
            str(jobs_path),
            "--approvals",
            str(approvals_path),
            "--confirm-human-deactivation",
        ],
    )

    exit_code = deactivate_merchant_job.main()

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["action"] == "deactivated"
    assert payload["approval_revoked"] is True
    assert called["job_id"] == "notino-de"
    assert called["jobs_path"] == jobs_path
    assert called["approvals_path"] == approvals_path
