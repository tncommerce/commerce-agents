"""Offline evidence regression: no provider calls, runtime queue or live analytics."""

import copy
import hashlib
import json

import pytest

from scripts.dufynd_free_acceptance import STAGES, FixtureChecker, coverage, maker_fixture
from scripts.dufynd_independent_checker import (
    CheckerIdentity,
    make_handoff,
    next_safe_task,
    run_checker,
)
from scripts.dufynd_worker_evidence import (
    ATTRIBUTION,
    CODE_WINDOWS,
    MAX_PROMPT_BYTES,
    MAX_SOURCE_BYTES,
    ROOT,
    encode,
    excerpt,
    pack_evidence,
    source_text,
)

TASK = {
    "task_id": "qa-consent-evidence",
    "domain": "research",
    "title": "Audit launch attribution with optional measurement",
    "instruction": "Audit attribution src cmp content sid clickout consent and withdrawal",
    "dependencies": [],
}


def test_repository_consent_coverage_fits_unchanged_budget():
    packet = pack_evidence(TASK, head="a" * 40)
    assert MAX_PROMPT_BYTES == 24576
    assert MAX_SOURCE_BYTES == 262144
    assert len(encode(packet)) <= MAX_PROMPT_BYTES
    assert all(coverage(packet).values()), packet["omitted_sources"]
    for source in packet["repository_evidence"]:
        raw = (ROOT / source["path"]).read_bytes()
        assert source["sha256"] == hashlib.sha256(raw).hexdigest()
        if source.get("omission_reason") == "code_windows_only":
            lines = raw.decode().splitlines(keepends=True)
            joined = "".join("".join(lines[a - 1 : b]) for a, b in source["line_ranges"])
            assert source["text"] == joined


@pytest.mark.parametrize("partial", [False, True])
def test_missing_repository_evidence_is_blocked_not_fabricated(tmp_path, partial):
    if partial:
        path = tmp_path / ATTRIBUTION[0]
        path.parent.mkdir(parents=True)
        path.write_text("export function appendAcquisitionAttribution() {}\n")
    packet = pack_evidence(TASK, head="a" * 40, root=tmp_path)
    output = maker_fixture(TASK, packet)
    parsed = json.loads(output)
    assert parsed["requested_actions"] == []
    sources = {s["path"]: s for s in packet["repository_evidence"]}
    for claim in parsed["claims"]:
        assert claim["citation"]["quote"] in source_text(sources[claim["citation"]["path"]])
    handoff = make_handoff(TASK, output, packet, maker="test-maker")
    receipt = run_checker(
        handoff, FixtureChecker(root=tmp_path), identity=CheckerIdentity("test-checker")
    )
    assert receipt["outcome"] == "needs_more_evidence"
    assert receipt["next_state"] == "blocked"
    assert receipt["owner_publish_allowed"] is False
    assert receipt["automatic_paid_retry"] is False
    assert (
        next_safe_task([TASK | {"task_id": "other", "status": "ready"}], TASK["task_id"], receipt)
        is None
    )


@pytest.mark.parametrize("stage", ["client_consent", "server_consent"])
def test_quote_coverage_does_not_accept_missing_consent_guard(stage):
    # Synthetic strings exercise the coverage algorithm only; never production evidence.
    sources = {}
    for path, needles in STAGES.values():
        sources.setdefault(path, []).extend(needles)
    packet = {
        "evidence_profile": "launch_attribution",
        "repository_evidence": [
            {"path": path, "text": "\n".join(needles), "sha256": "synthetic"}
            for path, needles in sources.items()
        ],
    }
    assert all(coverage(packet).values())
    bad = copy.deepcopy(packet)
    path, needles = STAGES[stage]
    source = next(s for s in bad["repository_evidence"] if s["path"] == path)
    source["text"] = source["text"].replace(needles[0], "missing-guard")
    assert not coverage(bad)[stage]


def test_hard_budget_and_missing_anchor_survive_large_input(tmp_path):
    raw = ("export function appendAcquisitionAttribution " + "x" * 20000 + "\n").encode()
    path = tmp_path / ATTRIBUTION[0]
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    packet = pack_evidence(TASK, head="a" * 40, root=tmp_path)
    assert len(encode(packet)) <= MAX_PROMPT_BYTES
    assert not all(coverage(packet).values())
    parsed = json.loads(maker_fixture(TASK, packet))
    assert parsed["requested_actions"] == []
    source = excerpt(b"no expected functions here\n", set(), ATTRIBUTION[0])
    assert source["missing_anchors"]
    assert not source["complete"]


def test_required_sources_precede_secondary_diagnostics():
    required = {path for path, _ in STAGES.values()}
    assert set(ATTRIBUTION[: len(required)]) == required
    assert all(path in CODE_WINDOWS for path in required)
