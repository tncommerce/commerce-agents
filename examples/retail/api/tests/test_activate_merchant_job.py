import json
import sys

from retail.api import activate_merchant_job


def test_activation_cli_requires_explicit_confirmation(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "activate_merchant_job",
            "notino-de",
        ],
    )

    exit_code = activate_merchant_job.main()

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 20
    assert payload["action"] == "hold"
    assert payload["reasons"] == ["explicit_human_activation_required"]


def test_confirmed_activation_calls_activation_service(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    jobs_path = tmp_path / "jobs.json"
    approvals_path = tmp_path / "approvals.json"

    called = {}

    def fake_activation(
        *,
        jobs_path,
        approvals_path,
        job_id,
    ):
        called["jobs_path"] = jobs_path
        called["approvals_path"] = approvals_path
        called["job_id"] = job_id

        return activate_merchant_job.MerchantJobActivationResult(
            action="activated",
            exit_code=0,
            reasons=[],
            job_id=job_id,
        )

    monkeypatch.setattr(
        activate_merchant_job,
        "activate_merchant_job",
        fake_activation,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "activate_merchant_job",
            "notino-de",
            "--jobs",
            str(jobs_path),
            "--approvals",
            str(approvals_path),
            "--confirm-human-activation",
        ],
    )

    exit_code = activate_merchant_job.main()

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["action"] == "activated"
    assert called["job_id"] == "notino-de"
    assert called["jobs_path"] == jobs_path
    assert called["approvals_path"] == approvals_path
