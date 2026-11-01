"""Guard the default-branch Jarvis dispatcher against shell interpolation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

WORKFLOW = Path(".github/workflows/dufynd-jarvis-dispatch.yml")


def _script(name: str) -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    block = text.split(f"      - name: {name}\n", 1)[1].split("\n      - name:", 1)[0]
    return textwrap.dedent(block.split("        run: |\n", 1)[1]).rstrip() + "\n"


def _run(tmp_path: Path, name: str, **settings: str) -> tuple[subprocess.CompletedProcess, list]:
    fake_python = tmp_path / "python"
    fake_python.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['DISPATCH_LOG'], 'a', encoding='utf-8') as out:\n"
        "    out.write(json.dumps(sys.argv[1:]) + '\\n')\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    log = tmp_path / "dispatch.jsonl"
    env = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ.get("PATH", ""),
        "DISPATCH_LOG": str(log),
        **settings,
    }
    process = subprocess.run(
        ["/bin/bash", "-c", _script(name)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    calls = [json.loads(row) for row in log.read_text().splitlines()] if log.exists() else []
    return process, calls


def test_manual_inputs_are_bound_to_step_environment_not_bash_source() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert workflow.count("DUFYND_APPROVAL_TOKEN: ${{ inputs.approval_token }}") == 2
    assert "DUFYND_BOUNDED_MAX_MINUTES: ${{ github.event_name" in workflow
    assert "DUFYND_BOUNDED_MAX_TASKS: ${{ github.event_name" in workflow
    for name in (
        "Validate explicit active-run approval",
        "Validate explicit Nightshift pilot approval",
        "Run Jarvis bounded Overnight Supervisor",
    ):
        script = _script(name)
        assert "${{ inputs." not in script
        assert "${{ github.event_name" not in script


def test_explicit_approval_tokens_remain_required_without_shell_execution(tmp_path: Path) -> None:
    modes = (
        ("Validate explicit active-run approval", "GO-JARVIS-ACTIVE", 20),
        ("Validate explicit Nightshift pilot approval", "GO-JARVIS-NIGHTSHIFT", 27),
    )
    marker = tmp_path / "untrusted-token-must-not-execute"
    for name, token, refused in modes:
        accepted, calls = _run(
            tmp_path, name, DUFYND_APPROVAL_TOKEN=token, GITHUB_EVENT_NAME="workflow_dispatch"
        )
        assert accepted.returncode == 0, accepted.stderr
        assert calls == []
        denied, calls = _run(
            tmp_path,
            name,
            DUFYND_APPROVAL_TOKEN=f"{token}$(touch {marker})",
            GITHUB_EVENT_NAME="workflow_dispatch",
        )
        assert denied.returncode == refused
        assert calls == []
        assert not marker.exists()


def test_nightshift_supervisor_numeric_inputs_are_bounded_and_shell_safe(tmp_path: Path) -> None:
    name = "Run Jarvis bounded Overnight Supervisor"
    args = {
        "DUFYND_BOUNDED_MAX_MINUTES": "300",
        "DUFYND_BOUNDED_MAX_TASKS": "8",
    }
    passed, calls = _run(tmp_path, name, **args)
    assert passed.returncode == 0, passed.stderr
    assert calls == [
        [
            "-m", "scripts.dufynd_jarvis_supervisor",
            "--max-minutes", "300", "--max-cycles", "20",
            "--idle-seconds", "300", "--max-idle-cycles", "60",
            "--max-tasks", "8", "--max-events", "5",
            "--worker-timeout-seconds", "600", "--max-retries", "1",
        ]
    ]
    marker = tmp_path / "untrusted-numeric-must-not-execute"
    for column, invalid in (
        ("DUFYND_BOUNDED_MAX_MINUTES", "0"),
        ("DUFYND_BOUNDED_MAX_MINUTES", "331"),
        ("DUFYND_BOUNDED_MAX_MINUTES", f"300$(touch {marker})"),
        ("DUFYND_BOUNDED_MAX_TASKS", "9"),
        ("DUFYND_BOUNDED_MAX_TASKS", f"8;touch {marker}"),
    ):
        failed, later_calls = _run(tmp_path, name, **{**args, column: invalid})
        assert failed.returncode == 22
        assert later_calls == calls
        assert not marker.exists()
