"""Execute existing dispatch steps with an offline gh transport."""

from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
FLAGS = (
    "DUFYND_PRIVATE_BROKER_ENABLED",
    "DUFYND_PRIVATE_RENDER_SERVICES_V2_ENABLED",
    "DUFYND_PRIVATE_RENDER_SERVICES_V2_AUTO_ENABLED",
)


def dispatch_steps():
    found = []
    for filename in ("dufynd-private-observer.yml", "dufynd-private-observer-watchdog.yml"):
        path = ROOT / ".github" / "workflows" / filename
        if not path.exists():
            continue
        workflow = yaml.safe_load(path.read_text())
        for job_name, job in workflow["jobs"].items():
            for step in job["steps"]:
                if "gh workflow run dufynd-private-observer.yml" in step.get("run", ""):
                    found.append(pytest.param(step, id=f"{filename}:{job_name}"))
    assert found, "The existing workflow must still contain a dispatch step"
    return found


def execute_dispatch(tmp_path, step, values, *, exit_code=0):
    for flag in FLAGS:
        assert step["env"][flag] == "${{ vars." + flag + " }}"
    assert step["env"]["GH_TOKEN"] == "${{ github.token }}"
    log = tmp_path / "calls.jsonl"
    stub = tmp_path / "gh"
    stub.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['GH_CALL_LOG'], 'a') as handle:\n"
        "    handle.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "sys.exit(int(os.environ['GH_STUB_EXIT']))\n"
    )
    stub.chmod(0o755)
    env = {
        "PATH": str(tmp_path) + os.pathsep + os.defpath,
        "GH_TOKEN": "offline-only",
        "GITHUB_REPOSITORY": "tncommerce/commerce-agents",
        "GH_CALL_LOG": str(log),
        "GH_STUB_EXIT": str(exit_code),
        **dict(zip(FLAGS, values, strict=True)),
    }
    result = subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-c", step["run"]],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return result, calls


def expected_call(enabled):
    return [
        "workflow",
        "run",
        "dufynd-private-observer.yml",
        "--repo",
        "tncommerce/commerce-agents",
        "--ref",
        "scentai-mvp",
        "-f",
        "mode=render_services_v2" if enabled else "mode=render",
        "-f",
        "capture_v2=true" if enabled else "capture_v2=false",
    ]


@pytest.mark.parametrize("step", dispatch_steps())
@pytest.mark.parametrize("values", list(itertools.product(("", "1"), repeat=3)))
def test_exactly_one_dispatch_and_capture_requires_all_gates(tmp_path, step, values):
    result, calls = execute_dispatch(tmp_path, step, values)
    assert result.returncode == 0, result.stderr
    assert calls == [expected_call(values == ("1", "1", "1"))]
    assert not result.stdout and not result.stderr


@pytest.mark.parametrize("step", dispatch_steps())
@pytest.mark.parametrize("flag_index", range(3))
@pytest.mark.parametrize("invalid", ["0", "true", "01", "1 ", "1\n", "$(exit 99)"])
def test_nonliteral_gate_values_keep_the_legacy_read(tmp_path, step, flag_index, invalid):
    values = ["1", "1", "1"]
    values[flag_index] = invalid
    result, calls = execute_dispatch(tmp_path, step, values)
    assert result.returncode == 0, result.stderr
    assert calls == [expected_call(False)]


@pytest.mark.parametrize("step", dispatch_steps())
def test_dispatch_transport_failure_is_visible_without_retry(tmp_path, step):
    result, calls = execute_dispatch(tmp_path, step, ("1", "1", "1"), exit_code=37)
    assert result.returncode == 37
    assert calls == [expected_call(True)]
