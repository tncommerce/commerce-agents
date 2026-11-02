"""Main-branch dispatch must reject unapproved Nightshift before state writes."""

from __future__ import annotations

from pathlib import Path

import yaml

PATH = Path(".github/workflows/dufynd-jarvis-dispatch.yml")


def test_main_nightshift_approval_precedes_refresh_sync_and_all_db_calls() -> None:
    doc = yaml.safe_load(PATH.read_text(encoding="utf-8"))
    job = doc["jobs"]["nightshift"]
    steps = job["steps"]
    names = [step.get("name") for step in steps]
    guard = names.index("Validate explicit Nightshift pilot approval")
    refresh = names.index("Refresh repository Jarvis state")
    sync = names.index("Sync Jarvis control plane")
    audit = names.index("Capture Jarvis control-plane audit")
    restore = names.index("Restore clean worker checkout after control-plane sync")
    assert guard < refresh < sync < audit < restore
    assert names.index("Run Jarvis bounded Overnight Supervisor") > restore
    approved = steps[guard]
    assert approved["shell"] == "bash"
    assert approved["env"]["DUFYND_APPROVAL_TOKEN"] == "${{ inputs.approval_token }}"
    assert "GO-JARVIS-NIGHTSHIFT" in approved["run"]
    assert 'if [ "${GITHUB_EVENT_NAME}" = "issue_comment" ]; then' in approved["run"]
    assert "${{ inputs." not in approved["run"]


def test_guarded_owner_pr_comment_signal_must_stay_exact() -> None:
    text = PATH.read_text(encoding="utf-8")
    assert "github.event.issue.number == 1" in text
    assert "github.actor == github.repository_owner" in text
    assert "github.event.comment.body == 'GO-JARVIS-NIGHTSHIFT'" in text
    assert "persist-credentials: false" in text
    assert "DUFYND_JARVIS_MAX_BUDGET_USD: \"0.25\"" in text


def test_main_process_next_approval_remains_before_runtime() -> None:
    doc = yaml.safe_load(PATH.read_text(encoding="utf-8"))
    steps = doc["jobs"]["jarvis"]["steps"]
    names = [step.get("name") for step in steps]
    assert names.index("Validate explicit active-run approval") < names.index(
        "Process one Jarvis event"
    )
    approval = steps[names.index("Validate explicit active-run approval")]
    assert "GO-JARVIS-ACTIVE" in approval["run"]
    assert "${{ inputs." not in approval["run"]
