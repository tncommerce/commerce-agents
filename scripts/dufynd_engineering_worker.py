from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    McpSdkServerConfig,
    SdkMcpTool,
    create_sdk_mcp_server,
    tool,
)
from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge

from commerce_common.agent_sdk import collect_turn

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_NAME = "dufynd_engineering_worker"
SERVER_VERSION = "0.1.0"
MAX_TEXT_BYTES = 250_000
MAX_READ_LINES = 500
MAX_SEARCH_RESULTS = 100
DEFAULT_MAX_TURNS = 12
HARD_MAX_TURNS = 20
DEFAULT_MAX_BUDGET_USD = 0.25
HARD_MAX_BUDGET_USD = 1.00

WRITE_PREFIXES = (
    "scripts/",
    "tests/",
    "docs/",
    "examples/retail/api/",
    "examples/retail/storefront-web/app/",
    "examples/retail/storefront-web/components/",
    "examples/retail/storefront-web/lib/",
    "examples/retail/storefront-web/scripts/",
    "examples/retail/storefront-web/tests/",
)
DENIED_WRITE_PREFIXES = (
    ".github/",
    "examples/retail/data/",
    "supabase/",
)
DENIED_PARTS = {
    ".git",
    ".env",
    "node_modules",
    ".next",
    "__pycache__",
    ".venv",
    "venv",
}
DENIED_FILENAMES = {
    ".npmrc",
    ".pypirc",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
}
DENIED_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}

SYSTEM_PROMPT = """\
You are the DUFYND Jarvis Engineering Worker.

Your job is to prepare high-quality technical patches in a disposable repository
checkout. Your changes are proposals only. You have no push, merge, deploy,
publishing, spending, contract, credential, or production-database tools.

Rules:
1. Read the current repo master status before choosing implementation work.
2. Keep changes narrowly scoped to the requested task.
3. Never modify GitHub workflows, canonical DUFYND data, dependency manifests,
   lockfiles, secrets, credentials, or Supabase schema from this worker.
4. Never use the network.
5. Use only the provided repository tools. Do not assume raw shell access exists.
6. Run only non-executing static checks after edits, then inspect the worktree diff.
   Executing modified repository code is reserved for a separate secret-free sandbox.
7. If a task needs a forbidden path/action, stop and report the exact escalation
   needed instead of bypassing the restriction.
8. Do not fabricate test success or claim a change was merged/deployed.
9. Prefer reversible implementation with tests.
10. DUFYND is the current public brand; SCENTAI is legacy naming only where the
    repository still requires it for compatibility.
"""


def _result(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def _json_result(payload: Any) -> dict[str, Any]:
    return _result(json.dumps(payload, ensure_ascii=False, default=str))


def _relative_repo_path(path: str) -> Path:
    raw = str(path or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("path is required")

    candidate = Path(raw)
    if candidate.is_absolute():
        raise ValueError("absolute paths are not allowed")

    resolved = (REPO_ROOT / candidate).resolve()
    try:
        relative = resolved.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("path must stay inside the repository") from exc

    if any(part in DENIED_PARTS for part in relative.parts):
        raise ValueError("path enters a denied repository area")
    if relative.suffix.lower() in DENIED_SUFFIXES:
        raise ValueError("sensitive key/certificate files are not accessible")
    if relative.name.startswith(".env"):
        raise ValueError("environment files are not accessible")
    if relative.name in DENIED_FILENAMES:
        raise ValueError("dependency/credential file access is not allowed in this worker")

    return relative


def _resolve_read_path(path: str) -> Path:
    relative = _relative_repo_path(path)
    resolved = REPO_ROOT / relative
    if not resolved.exists() or not resolved.is_file():
        raise ValueError(f"file does not exist: {relative.as_posix()}")
    return resolved


def _resolve_write_path(path: str) -> Path:
    relative = _relative_repo_path(path)
    normalized = relative.as_posix()

    if any(
        normalized == prefix.rstrip("/") or normalized.startswith(prefix)
        for prefix in DENIED_WRITE_PREFIXES
    ):
        raise ValueError("worker may not modify this protected path")
    if not any(normalized.startswith(prefix) for prefix in WRITE_PREFIXES):
        raise ValueError("worker write path is outside the approved engineering areas")

    return REPO_ROOT / relative


def _read_text(path: str, start_line: int = 1, end_line: int | None = None) -> dict[str, Any]:
    resolved = _resolve_read_path(path)
    if resolved.stat().st_size > MAX_TEXT_BYTES:
        raise ValueError("file is too large for the engineering worker")

    text = resolved.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = max(1, int(start_line))
    requested_end = int(end_line) if end_line is not None else start + MAX_READ_LINES - 1
    end = max(start, min(requested_end, start + MAX_READ_LINES - 1, len(lines)))

    selected = lines[start - 1 : end]
    return {
        "path": resolved.relative_to(REPO_ROOT).as_posix(),
        "start_line": start,
        "end_line": end,
        "total_lines": len(lines),
        "content": "\n".join(selected),
    }


def _search_text(pattern: str, path: str = ".") -> dict[str, Any]:
    if len(pattern) > 500:
        raise ValueError("search pattern is too long")
    regex = re.compile(pattern)

    relative_root = _relative_repo_path(path) if path != "." else Path(".")
    root = (REPO_ROOT / relative_root).resolve()
    if not root.exists():
        raise ValueError("search path does not exist")

    files = [root] if root.is_file() else root.rglob("*")
    matches: list[dict[str, Any]] = []

    for candidate in files:
        if len(matches) >= MAX_SEARCH_RESULTS:
            break
        if not candidate.is_file():
            continue
        try:
            relative = candidate.resolve().relative_to(REPO_ROOT.resolve())
        except ValueError:
            continue
        if any(part in DENIED_PARTS for part in relative.parts):
            continue
        if relative.name.startswith(".env"):
            continue
        if relative.name in DENIED_FILENAMES or relative.suffix.lower() in DENIED_SUFFIXES:
            continue
        if candidate.stat().st_size > MAX_TEXT_BYTES:
            continue
        try:
            lines = candidate.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue

        for number, line in enumerate(lines, start=1):
            if regex.search(line):
                matches.append(
                    {
                        "path": relative.as_posix(),
                        "line": number,
                        "text": line[:500],
                    }
                )
                if len(matches) >= MAX_SEARCH_RESULTS:
                    break

    return {
        "pattern": pattern,
        "path": relative_root.as_posix(),
        "matches": matches,
        "truncated": len(matches) >= MAX_SEARCH_RESULTS,
    }


def _write_text(path: str, content: str) -> dict[str, Any]:
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_TEXT_BYTES:
        raise ValueError("write exceeds engineering worker size limit")

    resolved = _resolve_write_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")

    return {
        "path": resolved.relative_to(REPO_ROOT).as_posix(),
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _replace_text(path: str, old: str, new: str, replace_all: bool = False) -> dict[str, Any]:
    if not old:
        raise ValueError("old text is required")
    resolved = _resolve_write_path(path)
    if not resolved.exists():
        raise ValueError("replace requires an existing file")
    if resolved.stat().st_size > MAX_TEXT_BYTES:
        raise ValueError("file is too large for the engineering worker")

    content = resolved.read_text(encoding="utf-8")
    occurrences = content.count(old)
    if occurrences == 0:
        raise ValueError("old text was not found")
    if occurrences > 1 and not replace_all:
        raise ValueError("old text is not unique; set replace_all=true deliberately")

    updated = content.replace(old, new) if replace_all else content.replace(old, new, 1)
    return _write_text(path, updated) | {"replacements": occurrences if replace_all else 1}


def _validate_check_target(target: str | None) -> str | None:
    if target is None or not str(target).strip():
        return None
    raw = str(target).strip()
    if raw.startswith("-"):
        raise ValueError("check target may not start with an option prefix")
    relative = _relative_repo_path(raw)
    resolved = REPO_ROOT / relative
    if not resolved.exists():
        raise ValueError("check target must exist inside the repository")
    return relative.as_posix()


def _run_command(command: list[str], *, timeout_seconds: int = 180) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    stdout = completed.stdout[-40_000:]
    stderr = completed.stderr[-20_000:]
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "success": completed.returncode == 0,
    }


def _run_safe_check(check: str, target: str | None = None) -> dict[str, Any]:
    target = _validate_check_target(target)

    if check == "git_status":
        if target is not None:
            raise ValueError("git_status does not accept a target")
        return _run_command(["git", "status", "--short"], timeout_seconds=30)

    if check == "git_diff":
        command = ["git", "diff", "--no-ext-diff", "--"]
        if target:
            command.append(target)
        return _run_command(command, timeout_seconds=30)

    if check == "ruff_check":
        command = ["ruff", "check", target or "."]
        return _run_command(command)

    if check == "ruff_format_check":
        command = ["ruff", "format", "--check", target or "."]
        return _run_command(command)

    raise ValueError(
        "unsupported check; use git_status, git_diff, ruff_check, or ruff_format_check"
    )


def build_tools() -> list[SdkMcpTool[Any]]:
    @tool(
        "load_repo_master_status",
        "Load the current repository-derived DUFYND Jarvis master status.",
        {},
    )
    async def load_repo_master_status(_args: dict[str, Any]) -> dict[str, Any]:
        return _json_result(
            await asyncio.to_thread(
                _read_text,
                "examples/retail/data/scentai_jarvis_master_status.json",
                1,
                MAX_READ_LINES,
            )
        )

    @tool(
        "read_repo_file",
        "Read a bounded line range from a non-sensitive repository text file.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
            },
            "required": ["path"],
        },
    )
    async def read_repo_file(args: dict[str, Any]) -> dict[str, Any]:
        return _json_result(
            await asyncio.to_thread(
                _read_text,
                args["path"],
                int(args.get("start_line", 1)),
                args.get("end_line"),
            )
        )

    @tool(
        "search_repo_text",
        "Regex-search repository text files with bounded output.",
        {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["pattern"],
        },
    )
    async def search_repo_text(args: dict[str, Any]) -> dict[str, Any]:
        return _json_result(
            await asyncio.to_thread(
                _search_text,
                args["pattern"],
                args.get("path", "."),
            )
        )

    @tool(
        "write_repo_file",
        "Write UTF-8 text only inside approved engineering paths in the disposable checkout.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    )
    async def write_repo_file(args: dict[str, Any]) -> dict[str, Any]:
        return _json_result(await asyncio.to_thread(_write_text, args["path"], args["content"]))

    @tool(
        "replace_repo_text",
        "Replace exact text inside an approved engineering file.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old": {"type": "string"},
                "new": {"type": "string"},
                "replace_all": {"type": "boolean"},
            },
            "required": ["path", "old", "new"],
        },
    )
    async def replace_repo_text(args: dict[str, Any]) -> dict[str, Any]:
        return _json_result(
            await asyncio.to_thread(
                _replace_text,
                args["path"],
                args["old"],
                args["new"],
                bool(args.get("replace_all", False)),
            )
        )

    @tool(
        "run_safe_check",
        "Run one allowlisted local repository check without shell interpretation or network access.",
        {
            "type": "object",
            "properties": {
                "check": {
                    "type": "string",
                    "enum": [
                        "git_status",
                        "git_diff",
                        "ruff_check",
                        "ruff_format_check",
                    ],
                },
                "target": {"type": "string"},
            },
            "required": ["check"],
        },
    )
    async def run_safe_check(args: dict[str, Any]) -> dict[str, Any]:
        return _json_result(
            await asyncio.to_thread(
                _run_safe_check,
                args["check"],
                args.get("target"),
            )
        )

    return [
        load_repo_master_status,
        read_repo_file,
        search_repo_text,
        write_repo_file,
        replace_repo_text,
        run_safe_check,
    ]


def build_server() -> McpSdkServerConfig:
    return create_sdk_mcp_server(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        tools=build_tools(),
    )


def allowed_tool_names() -> list[str]:
    names = (
        "load_repo_master_status",
        "read_repo_file",
        "search_repo_text",
        "write_repo_file",
        "replace_repo_text",
        "run_safe_check",
    )
    return [f"mcp__{SERVER_NAME}__{name}" for name in names]


def runtime_readiness() -> dict[str, Any]:
    active = os.getenv("DUFYND_ENGINEERING_WORKER_ACTIVE") == "1"
    model = os.getenv("DUFYND_ENGINEERING_WORKER_MODEL") or os.getenv("DUFYND_JARVIS_MODEL")
    credentials = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))
    supabase = bool(
        os.getenv("SUPABASE_URL")
        and (os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    )
    budget_id = os.getenv("DUFYND_ENGINEERING_WORKER_BUDGET_ID") or os.getenv(
        "DUFYND_JARVIS_BUDGET_ID"
    )

    return {
        "active": active,
        "model_configured": bool(model),
        "model": model,
        "anthropic_credentials_configured": credentials,
        "supabase_configured": supabase,
        "budget_id": budget_id,
        "max_turns": os.getenv("DUFYND_ENGINEERING_WORKER_MAX_TURNS", str(DEFAULT_MAX_TURNS)),
        "max_budget_usd": os.getenv(
            "DUFYND_ENGINEERING_WORKER_MAX_BUDGET_USD",
            str(DEFAULT_MAX_BUDGET_USD),
        ),
        "ready_for_model_execution": active
        and bool(model)
        and credentials
        and supabase
        and bool(budget_id),
        "push_capability": False,
        "merge_capability": False,
        "network_tool_capability": False,
    }


def _require_active_runtime() -> tuple[str, int, float]:
    readiness = runtime_readiness()
    if not readiness["active"]:
        raise RuntimeError(
            "DUFYND engineering worker is disabled. "
            "Set DUFYND_ENGINEERING_WORKER_ACTIVE=1 only after operator approval."
        )
    if not readiness["model_configured"]:
        raise RuntimeError("DUFYND engineering worker model is required.")
    if not readiness["anthropic_credentials_configured"]:
        raise RuntimeError("Anthropic credentials are required.")

    try:
        max_turns = int(readiness["max_turns"])
    except ValueError as error:
        raise RuntimeError("DUFYND_ENGINEERING_WORKER_MAX_TURNS must be an integer.") from error

    try:
        max_budget_usd = float(readiness["max_budget_usd"])
    except ValueError as error:
        raise RuntimeError("DUFYND_ENGINEERING_WORKER_MAX_BUDGET_USD must be numeric.") from error

    if max_budget_usd <= 0:
        raise RuntimeError("engineering worker max budget must be greater than zero")

    return (
        str(readiness["model"]),
        max(4, min(max_turns, HARD_MAX_TURNS)),
        min(max_budget_usd, HARD_MAX_BUDGET_USD),
    )


def _require_budget_window(
    bridge: DufyndJarvisBridge,
    model: str,
) -> tuple[str, dict[str, Any]]:
    budget_id = os.getenv("DUFYND_ENGINEERING_WORKER_BUDGET_ID") or os.getenv(
        "DUFYND_JARVIS_BUDGET_ID"
    )
    if not budget_id:
        raise RuntimeError("engineering worker budget window id is required")

    status = bridge.load_budget_status(budget_id)
    if not status.get("can_run"):
        raise RuntimeError(
            "DUFYND engineering worker budget window does not permit another run: "
            + json.dumps(status, ensure_ascii=False, default=str)
        )

    budget_model = status.get("model")
    if budget_model and budget_model != model:
        raise RuntimeError(f"engineering worker budget requires model {budget_model}, not {model}")

    return budget_id, status


def make_options() -> ClaudeAgentOptions:
    model, max_turns, max_budget_usd = _require_active_runtime()
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={SERVER_NAME: build_server()},
        allowed_tools=allowed_tool_names(),
        tools=[],
        cwd=REPO_ROOT,
        env={"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1"},
        model=model,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        permission_mode="dontAsk",
    )


async def run_once(
    prompt: str,
    bridge: DufyndJarvisBridge,
) -> tuple[str, float | None, str]:
    model, _, _ = _require_active_runtime()
    budget_id, _ = await asyncio.to_thread(_require_budget_window, bridge, model)

    async with ClaudeSDKClient(options=make_options()) as client:
        await client.query(prompt)
        result = await collect_turn(client)

    if result.is_error:
        detail = "; ".join(result.tool_errors) or result.text or "engineering worker failed"
        raise RuntimeError(detail)

    await asyncio.to_thread(
        bridge.record_run,
        run_type="engineering_patch",
        input_summary=prompt[:4000],
        output_summary=result.text[:8000] or "(engineering worker produced no prose output)",
        decisions=[
            {
                "cost_usd": result.cost_usd,
                "budget_id": budget_id,
                "runtime": "dufynd_engineering_worker_v0_1",
            }
        ],
        human_approval_required=False,
        agent_name="jarvis_engineering",
    )
    return result.text.strip(), result.cost_usd, budget_id


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DUFYND Jarvis engineering worker for disposable patch preparation."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--readiness", action="store_true")
    group.add_argument("--once", metavar="PROMPT")
    args = parser.parse_args()

    if args.readiness:
        print(json.dumps(runtime_readiness(), ensure_ascii=False))
        return 0

    bridge = DufyndJarvisBridge()
    text, cost_usd, _ = asyncio.run(run_once(args.once, bridge))
    if text:
        print(text)
    if cost_usd is not None:
        print(f"[Engineering worker cost: USD {cost_usd:.4f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
