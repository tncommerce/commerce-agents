"""Synthetic local checkpoints only; no private source, dispatch or network."""

import copy
import json

import pytest
from scripts.dufynd_seven_content_workers import EditorialRunner, WorkerInputError
from tests.test_dufynd_seven_content_workers import editorial_fixture


@pytest.fixture
def checkpoint(tmp_path):
    path = tmp_path / "private.json"
    runner = EditorialRunner(
        round_id="dufynd_editorial_resume_integrity",
        pilot=editorial_fixture(),
        existing={},
        checkpoint=path,
    )
    state = runner.run()
    return runner, path, state


@pytest.mark.parametrize(
    "field,value",
    [
        ("state", "DONE"),
        ("holds", []),
        ("cost_eur", 1),
        ("name", "Changed role"),
    ],
)
def test_metadata_corruption_cannot_resume(checkpoint, field, value):
    runner, path, state = checkpoint
    state["role_packets"]["W3"][field] = value
    path.write_text(json.dumps(state))
    before = path.read_bytes()
    with pytest.raises(WorkerInputError, match="checkpoint_packet_integrity_failed"):
        runner.run()
    assert path.read_bytes() == before


def test_valid_legacy_checkpoint_is_verified_and_bound_once(checkpoint):
    runner, path, state = checkpoint
    for saved in state["role_packets"].values():
        saved.pop("packet_sha256", None)
    path.write_text(json.dumps(state))
    upgraded = runner.run()
    assert all(len(p["packet_sha256"]) == 64 for p in upgraded["role_packets"].values())
    before = path.read_bytes()
    assert runner.run() == upgraded
    assert path.read_bytes() == before


def test_removing_hash_cannot_bless_modified_legacy_packet(checkpoint):
    runner, path, state = checkpoint
    for saved in state["role_packets"].values():
        saved.pop("packet_sha256", None)
    state["role_packets"]["W3"].update(state="DONE", holds=[], cost_eur=1)
    path.write_text(json.dumps(state))
    with pytest.raises(WorkerInputError, match="checkpoint_packet_integrity_failed"):
        runner.run()


def test_legacy_dependency_hold_must_match_actual_missing_roles(tmp_path):
    pilot = copy.deepcopy(editorial_fixture())
    pilot["W5"]["questions"] = []
    path = tmp_path / "blocked.json"
    runner = EditorialRunner(
        round_id="dufynd_editorial_dependency_hold", pilot=pilot, existing={}, checkpoint=path
    )
    state = runner.run()
    for saved in state["role_packets"].values():
        saved.pop("packet_sha256", None)
    path.write_text(json.dumps(state))
    assert runner.run()["role_packets"]["W6"]["state"] == "BLOCKED"
    state["role_packets"]["W6"]["holds"] = []
    path.write_text(json.dumps(state))
    with pytest.raises(WorkerInputError, match="checkpoint_packet_integrity_failed"):
        runner.run()
