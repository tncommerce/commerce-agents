"""Execute the real workflow handoff against local, non-network command doubles."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(".github/workflows/dufynd-jarvis-manual.yml")


def handoff(tmp_path: Path, *, ref: str = "scentai-mvp", stale: bool = False, patch=True):
    workflow = yaml.safe_load(WORKFLOW.read_text())
    step = next(
        s
        for s in workflow["jobs"]["jarvis"]["steps"]
        if s.get("name") == "Create validated Jarvis worker PR"
    )
    assert step["if"] == (
        "inputs.mode == 'process-branch-task-pr' || inputs.mode == 'nightshift-pilot'"
    )
    binaries = tmp_path / "bin"
    binaries.mkdir()
    log = tmp_path / "commands.jsonl"
    fake = """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["HANDOFF_COMMAND_LOG"], "a") as f:
    f.write(json.dumps([name, *args]) + "\\n")
if name == "git" and args[:1] == ["rev-parse"]:
    print("different" if args[-1] == "origin/scentai-mvp" and os.environ["STALE_BASE"] == "1" else "base")
elif name == "gh" and args[:2] == ["pr", "create"]:
    print("https://github.invalid/acme/repo/pull/1")
"""
    for name in ("git", "gh"):
        executable = binaries / name
        executable.write_text(fake)
        executable.chmod(0o700)
    if patch:
        (tmp_path / "jarvis-worker-files.txt").write_text("examples/retail/api/example.py\n")
    env = {
        "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
        "GITHUB_REF_NAME": ref,
        "GITHUB_RUN_ID": "42",
        "GITHUB_RUN_ATTEMPT": "1",
        "HANDOFF_COMMAND_LOG": str(log),
        "STALE_BASE": "1" if stale else "0",
    }
    result = subprocess.run(
        ["bash", "-c", step["run"]],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    commands = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return result, commands


def test_validated_patch_creates_only_a_draft_on_the_production_base(tmp_path):
    result, commands = handoff(tmp_path)
    assert result.returncode == 0, result.stderr
    create = next(c for c in commands if c[:3] == ["gh", "pr", "create"])
    assert "--draft" in create
    assert create[create.index("--base") + 1] == "scentai-mvp"
    assert create[create.index("--head") + 1] == "jarvis/worker-42-1"
    pushes = [c for c in commands if c[:2] == ["git", "push"]]
    assert pushes == [["git", "push", "origin", "HEAD:refs/heads/jarvis/worker-42-1"]]
    assert not any(c[:3] == ["gh", "pr", "merge"] for c in commands)


@pytest.mark.parametrize("ref", ["main", "unreviewed-dev"])
def test_handoff_refuses_other_dispatch_branches(tmp_path, ref):
    result, commands = handoff(tmp_path, ref=ref)
    assert result.returncode == 25
    assert commands == []


def test_handoff_refuses_a_base_that_moved_during_validation(tmp_path):
    result, commands = handoff(tmp_path, stale=True)
    assert result.returncode == 26
    assert not any(c[:2] == ["git", "push"] or c[0] == "gh" for c in commands)


def test_no_patch_does_not_create_an_empty_pr(tmp_path):
    result, commands = handoff(tmp_path, patch=False)
    assert result.returncode == 0
    assert commands == []
