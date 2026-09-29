from __future__ import annotations

from pathlib import Path

import pytest

import scripts.dufynd_engineering_worker as worker


class BudgetBridge:
    def __init__(self, *, can_run: bool = True, model: str = "claude-sonnet-5"):
        self.can_run = can_run
        self.model = model

    def load_budget_status(self, budget_id: str):
        return {
            "budget_id": budget_id,
            "status": "active" if self.can_run else "planned",
            "model": self.model,
            "can_run": self.can_run,
        }


def test_worker_exposes_only_restricted_custom_tools() -> None:
    names = worker.allowed_tool_names()

    assert "mcp__dufynd_engineering_worker__read_repo_file" in names
    assert "mcp__dufynd_engineering_worker__write_repo_file" in names
    assert "mcp__dufynd_engineering_worker__run_safe_check" in names
    assert all(name.startswith("mcp__dufynd_engineering_worker__") for name in names)
    assert all("bash" not in name.lower() for name in names)
    assert all("push" not in name.lower() for name in names)
    assert all("merge" not in name.lower() for name in names)


def test_worker_write_allowlist_blocks_protected_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(worker, "REPO_ROOT", tmp_path)

    assert worker._resolve_write_path("scripts/new_worker_helper.py") == (
        tmp_path / "scripts/new_worker_helper.py"
    )

    with pytest.raises(ValueError, match="protected path"):
        worker._resolve_write_path(".github/workflows/ci.yml")

    with pytest.raises(ValueError, match="protected path"):
        worker._resolve_write_path("examples/retail/data/merchant_offers.json")

    with pytest.raises(ValueError, match="approved engineering areas"):
        worker._resolve_write_path("README.md")


def test_worker_blocks_dependency_and_secret_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(worker, "REPO_ROOT", tmp_path)

    with pytest.raises(ValueError, match="dependency/lockfile"):
        worker._relative_repo_path("requirements.txt")

    with pytest.raises(ValueError, match="sensitive key"):
        worker._relative_repo_path("scripts/private.pem")

    with pytest.raises(ValueError, match="denied repository area"):
        worker._relative_repo_path(".git/config")


def test_worker_blocks_path_escape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(worker, "REPO_ROOT", tmp_path)

    with pytest.raises(ValueError, match="inside the repository"):
        worker._relative_repo_path("../outside.txt")

    with pytest.raises(ValueError, match="absolute paths"):
        worker._relative_repo_path("/tmp/outside.txt")


def test_worker_write_and_replace_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(worker, "REPO_ROOT", tmp_path)

    result = worker._write_text("tests/example.txt", "alpha\nbeta\n")
    assert result["bytes"] == len("alpha\nbeta\n".encode())
    assert (tmp_path / "tests/example.txt").read_text() == "alpha\nbeta\n"

    replaced = worker._replace_text("tests/example.txt", "beta", "gamma")
    assert replaced["replacements"] == 1
    assert (tmp_path / "tests/example.txt").read_text() == "alpha\ngamma\n"


def test_worker_replace_requires_unique_match_by_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(worker, "REPO_ROOT", tmp_path)
    worker._write_text("tests/example.txt", "x\nx\n")

    with pytest.raises(ValueError, match="not unique"):
        worker._replace_text("tests/example.txt", "x", "y")


def test_worker_safe_checks_use_fixed_command_argv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(worker, "REPO_ROOT", tmp_path)
    seen = []

    def fake_run(command, *, timeout_seconds=180):
        seen.append((command, timeout_seconds))
        return {"command": command, "exit_code": 0, "success": True}

    monkeypatch.setattr(worker, "_run_command", fake_run)

    worker._run_safe_check("pytest", "tests/test_worker.py::test_one")
    worker._run_safe_check("git_diff", "scripts/example.py")
    worker._run_safe_check("repo_check")

    assert seen[0][0] == ["pytest", "-q", "tests/test_worker.py::test_one"]
    assert seen[1][0] == [
        "git",
        "diff",
        "--no-ext-diff",
        "--",
        "scripts/example.py",
    ]
    assert seen[2][0][1:] == ["scripts/check.py"]


def test_worker_rejects_unknown_check() -> None:
    with pytest.raises(ValueError, match="unsupported check"):
        worker._run_safe_check("curl")


def test_worker_readiness_is_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "DUFYND_ENGINEERING_WORKER_ACTIVE",
        "DUFYND_ENGINEERING_WORKER_MODEL",
        "DUFYND_JARVIS_MODEL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "DUFYND_ENGINEERING_WORKER_BUDGET_ID",
        "DUFYND_JARVIS_BUDGET_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    readiness = worker.runtime_readiness()

    assert readiness["active"] is False
    assert readiness["ready_for_model_execution"] is False
    assert readiness["push_capability"] is False
    assert readiness["merge_capability"] is False
    assert readiness["network_tool_capability"] is False


def test_worker_runtime_clamps_turns_and_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DUFYND_ENGINEERING_WORKER_ACTIVE", "1")
    monkeypatch.setenv("DUFYND_ENGINEERING_WORKER_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret")
    monkeypatch.setenv("DUFYND_ENGINEERING_WORKER_BUDGET_ID", "budget_test")
    monkeypatch.setenv("DUFYND_ENGINEERING_WORKER_MAX_TURNS", "999")
    monkeypatch.setenv("DUFYND_ENGINEERING_WORKER_MAX_BUDGET_USD", "5")

    model, max_turns, max_budget = worker._require_active_runtime()

    assert model == "claude-sonnet-5"
    assert max_turns == worker.HARD_MAX_TURNS
    assert max_budget == worker.HARD_MAX_BUDGET_USD


def test_worker_requires_active_budget_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DUFYND_ENGINEERING_WORKER_BUDGET_ID", "budget_test")

    budget_id, status = worker._require_budget_window(
        BudgetBridge(can_run=True),
        "claude-sonnet-5",
    )

    assert budget_id == "budget_test"
    assert status["can_run"] is True

    with pytest.raises(RuntimeError, match="does not permit another run"):
        worker._require_budget_window(
            BudgetBridge(can_run=False),
            "claude-sonnet-5",
        )


def test_worker_budget_model_must_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DUFYND_ENGINEERING_WORKER_BUDGET_ID", "budget_test")

    with pytest.raises(RuntimeError, match="requires model"):
        worker._require_budget_window(
            BudgetBridge(can_run=True, model="claude-opus-5"),
            "claude-sonnet-5",
        )
