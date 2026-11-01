"""Fail-closed checks for untrusted GitHub workflow_dispatch shell inputs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(".github/workflows/dufynd-jarvis-manual.yml")


def _step(name: str) -> dict:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return next(step for step in workflow["jobs"]["jarvis"]["steps"] if step.get("name") == name)


def _invoke(tmp_path: Path, name: str, **inputs: str) -> tuple[subprocess.CompletedProcess, list]:
    step = _step(name)
    python_stub = tmp_path / "python"
    python_stub.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['DUFYND_TEST_LOG'], 'a', encoding='utf-8') as out:\n"
        "    out.write(json.dumps(sys.argv[1:]) + '\\n')\n",
        encoding="utf-8",
    )
    python_stub.chmod(0o755)
    log = tmp_path / "python-calls.jsonl"
    env = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ.get("PATH", ""),
        "DUFYND_TEST_LOG": str(log),
        **inputs,
    }
    result = subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-c", step["run"]],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return result, calls


def test_workflow_dispatch_values_never_interpolate_into_shell_source() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            assert "${{ inputs." not in step.get("run", ""), step.get("name")
    for name in ("Validate explicit active-run approval", "Validate explicit Nightshift pilot approval"):
        assert _step(name)["env"]["DUFYND_APPROVAL_TOKEN"] == "${{ inputs.approval_token }}"
    assert _step("Run bounded Jarvis supervisor")["env"]["DUFYND_MAX_EVENTS"] == "${{ inputs.max_events }}"
    assert _step("Run Jarvis Nightshift pilot")["env"]["DUFYND_NIGHTSHIFT_MAX_TASKS"] == (
        "${{ inputs.nightshift_max_tasks }}"
    )


@pytest.mark.parametrize(
    ("name", "approval", "refusal"),
    [
        ("Validate explicit active-run approval", "GO-JARVIS-ACTIVE", 20),
        ("Validate explicit Nightshift pilot approval", "GO-JARVIS-NIGHTSHIFT", 27),
    ],
)
def test_approval_token_is_data_not_executable_shell(tmp_path: Path, name: str, approval: str, refusal: int) -> None:
    good, calls = _invoke(tmp_path, name, DUFYND_APPROVAL_TOKEN=approval)
    assert good.returncode == 0, good.stderr
    assert calls == []

    marker = tmp_path / "command-substitution-must-not-run"
    payload = f"{approval}$(touch {marker})"
    denied, calls = _invoke(tmp_path, name, DUFYND_APPROVAL_TOKEN=payload)
    assert denied.returncode == refusal
    assert calls == []
    assert not marker.exists()


@pytest.mark.parametrize(
    ("name", "variable", "valid", "invalid", "expected_args"),
    [
        (
            "Run bounded Jarvis supervisor",
            "DUFYND_MAX_EVENTS",
            "8",
            "33",
            ["-m", "scripts.dufynd_jarvis_runtime", "--process-loop", "--max-events", "8"],
        ),
        (
            "Run Jarvis Nightshift pilot",
            "DUFYND_NIGHTSHIFT_MAX_TASKS",
            "8",
            "9",
            [
                "-m",
                "scripts.dufynd_jarvis_nightshift",
                "run",
                "--max-tasks",
                "8",
                "--max-events",
                "2",
                "--worker-timeout-seconds",
                "600",
                "--max-retries",
                "1",
            ],
        ),
    ],
)
def test_bounded_worker_input_does_not_execute_injected_shell(
    tmp_path: Path,
    name: str,
    variable: str,
    valid: str,
    invalid: str,
    expected_args: list[str],
) -> None:
    accepted, calls = _invoke(tmp_path, name, **{variable: valid})
    assert accepted.returncode == 0, accepted.stderr
    assert calls == [expected_args]

    marker = tmp_path / "input-injection-must-not-run"
    for rejected in ("0", invalid, f"8$(touch {marker})", f"8; touch {marker}"):
        denied, calls = _invoke(tmp_path, name, **{variable: rejected})
        assert denied.returncode == 22, (name, rejected, denied.stderr)
        assert calls == [expected_args]
        assert not marker.exists()
