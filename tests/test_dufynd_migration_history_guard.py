"""Offline migration-history contract: no DB or network dependencies."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.check_dufynd_migration_history import compare_histories, main


@pytest.fixture
def migration_dir(tmp_path: Path) -> Path:
    path = tmp_path / "migrations"
    path.mkdir()
    (path / "20261023221100_dufynd_runtime_offer_snapshots_v1.sql").write_text(
        "-- existing schema\n", encoding="utf-8"
    )
    return path


def history(version: str = "20261023221100", name: str = "dufynd_runtime_offer_snapshots_v1"):
    return {"migrations": [{"version": version, "name": name}]}


def test_exact_pairs_are_review_only_not_production_approval(migration_dir: Path) -> None:
    report = compare_histories(migration_dir, history())
    assert report["status"] == "ALIGNED_REVIEW_ONLY"
    assert report["exact_pairs"] == 1
    assert report["safe_to_run_db_push"] is None
    assert report["database_writes"] == 0
    assert report["automatic_repair_attempted"] is False


def test_real_schema_history_replay_is_blocked(migration_dir: Path) -> None:
    report = compare_histories(migration_dir, history("20261031200428"))
    assert report["status"] == "BLOCKED_MIGRATION_HISTORY_DRIFT"
    assert report["version_mismatch_same_name"] == [
        {
            "name": "dufynd_runtime_offer_snapshots_v1",
            "local": "20261023221100",
            "remote": "20261031200428",
        }
    ]
    assert report["safe_to_run_db_push"] is False


def test_duplicate_remote_names_are_never_assumed_aligned(migration_dir: Path) -> None:
    data = history()
    data["migrations"].append(
        {"version": "20261031200548", "name": "dufynd_runtime_offer_snapshots_v1"}
    )
    report = compare_histories(migration_dir, data)
    assert report["status"] == "BLOCKED_MIGRATION_HISTORY_DRIFT"
    assert report["duplicate_remote_names"] == ["dufynd_runtime_offer_snapshots_v1"]


def test_remote_only_and_local_only_both_block(migration_dir: Path) -> None:
    (migration_dir / "20261031010101_dufynd_second.sql").write_text("-- no-op\n")
    data = history()
    data["migrations"].append({"version": "20261031200548", "name": "dufynd_acl"})
    report = compare_histories(migration_dir, data)
    assert report["local_only_names"] == ["dufynd_second"]
    assert report["remote_only_names"] == ["dufynd_acl"]
    assert report["status"] == "BLOCKED_MIGRATION_HISTORY_DRIFT"


@pytest.mark.parametrize(
    "remote",
    [None, [], {}, {"migrations": []}, {"migrations": [{}]}, {"migrations": [False]}],
)
def test_missing_or_bad_remote_evidence_rejected(migration_dir: Path, remote) -> None:
    with pytest.raises(ValueError):
        compare_histories(migration_dir, remote)


def test_invalid_local_migration_filename_rejected(migration_dir: Path) -> None:
    (migration_dir / "not_a_migration.sql").write_text("-- unexpected\n")
    with pytest.raises(ValueError, match="local_migration_filename_invalid"):
        compare_histories(migration_dir, history())


def test_cli_returns_nonzero_without_sql_or_credentials(
    migration_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    import sys

    source = tmp_path / "remote.json"
    source.write_text(json.dumps(history("20261031200428")))
    monkeypatch.setattr(
        sys,
        "argv",
        ["audit", "--local-dir", str(migration_dir), "--remote-json", str(source)],
    )
    assert main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["database_writes"] == 0
    assert result["safe_to_run_db_push"] is False


def test_cli_invalid_json_never_claims_safe(
    migration_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    import sys

    source = tmp_path / "remote.json"
    source.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["audit", "--local-dir", str(migration_dir), "--remote-json", str(source)],
    )
    assert main() == 2
    assert json.loads(capsys.readouterr().out)["status"] == "BLOCKED_INPUT_INVALID"
