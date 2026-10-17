"""Interruption-safe private review artifacts; no database or provider required."""

import json

import pytest
from scripts.dufynd_content7_activation import write_private_output


@pytest.mark.parametrize("failure", ["serialize", "flush", "replace"])
def test_private_output_failure_preserves_reviewed_plan(tmp_path, monkeypatch, failure):
    from scripts import dufynd_content7_activation as activation

    path = tmp_path / "plan.json"
    previous = b'{"reviewed":"prior complete plan"}'
    path.write_bytes(previous)

    def interrupted(*args):
        raise OSError("injected interrupted write")

    value = {"plan": "new private editorial input"}
    if failure == "serialize":
        value["invalid"] = object()
    else:
        monkeypatch.setattr(
            activation.os, "fsync" if failure == "flush" else "replace", interrupted
        )
    with pytest.raises((TypeError, OSError)):
        write_private_output(path, value)
    assert path.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [path]


def test_private_output_replaces_complete_plan_with_private_permissions(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text("old")
    path.chmod(0o644)
    value = {"plan": {"title": "Prüfbarer neuer Plan"}, "plan_sha256": "example"}
    write_private_output(path, value)
    assert json.loads(path.read_text(encoding="utf-8")) == value
    assert path.stat().st_mode & 0o777 == 0o600
    assert list(tmp_path.iterdir()) == [path]
