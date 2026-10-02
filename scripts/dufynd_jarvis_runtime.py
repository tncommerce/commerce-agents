from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from contextlib import suppress
from functools import wraps
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
from scripts.dufynd_jarvis_context_pages import context_overview, context_page
from scripts.dufynd_jarvis_control_plane import HUMAN_REASONS, human_gate_allowed

from commerce_common.agent_sdk import collect_turn

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_NAME = "dufynd_jarvis"
SERVER_VERSION = "0.1.0"

DEFAULT_SUPERVISOR_MAX_EVENTS = 8
HARD_SUPERVISOR_MAX_EVENTS = 20
DEFAULT_AUTONOMOUS_MAX_EVENTS = 2
HARD_AUTONOMOUS_MAX_EVENTS = 5


class JarvisTurnError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        cost_usd: float | None = None,
        budget_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.cost_usd = cost_usd
        self.budget_id = budget_id


SYSTEM_PROMPT = """\
You are Jarvis, the internal operating and learning agent for DUFYND, operated by
TNCommerce.

Your job in this runtime is internal learning and preparation only. You do not
publish content, spend money, buy subscriptions or credits, merge production
code, send important outbound messages, sign contracts, place supplier orders,
or make destructive production changes. Those actions remain explicit human
approval gates and no tools for them are available here.

DUFYND is the current public brand. SCENTAI is historical/legacy only.

Operating rules:
1. Ground yourself in the current DUFYND context before making durable changes.
2. Treat references as evidence for reusable creative mechanisms, not templates
   to copy shot-for-shot.
3. Reuse existing creative patterns before creating a new pattern.
4. Protect exact product identity: final readable bottle/label frames and DUFYND
   typography must be deterministic, not invented by a generative video model.
5. Optimize for qualified attention, DUFYND brand memory and conversion fit,
   not unrelated views.
6. Separate observed evidence from hypotheses.
7. A single attractive render does not prove a repeatable workflow.
8. Store only durable, reusable lessons. Do not create duplicate ideas or
   duplicate patterns merely to show activity. New runtime-created ids must use
   the prefixes jarvis_pattern_, jarvis_idea_ and jarvis_lesson_ respectively.
9. If the event contains no genuinely new learning, say so and record the run
   without fabricating changes.
10. Keep the operator as final decision-maker for the high-impact gates above.

For a creative reference event:
- load the bounded creative pattern index first
- context loaders return section inventories; use load_context_page when the
  index is insufficient or lessons and reference details are needed
- follow next_offset until the relevant section is complete; if sha256 changes
  between pages, restart the section rather than mixing snapshots
- inspect existing patterns and lessons before making changes
- identify the reusable mechanisms
- link the reference to existing patterns where possible
- create a new pattern only when truly distinct
- create at most three original DUFYND adaptations when they add value
- link every new Jarvis-created idea to the reusable patterns it actually uses
- record a concise knowledge event describing what changed

For a performance event:
- compare observed outcomes with the existing creative hypothesis
- derive a durable lesson only when evidence is strong enough
- do not overgeneralize from one weak data point

For a bootstrap/context-sync event:
- load current context
- check that the knowledge graph is coherent
- do not duplicate already-normalized knowledge
- state the current learning boundary and next evidence needed
"""


def _result(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def _json_result(payload: Any) -> dict[str, Any]:
    return _result(json.dumps(payload, ensure_ascii=False, default=str))


def _require_runtime_id(value: str, prefix: str) -> str:
    if not value.startswith(prefix):
        raise ValueError(f"Jarvis-created ids must start with {prefix}")
    return value


def build_tools(bridge: DufyndJarvisBridge) -> list[SdkMcpTool[Any]]:
    @tool(
        "load_operating_context",
        "Load a bounded section inventory of the internal DUFYND operating context.",
        {},
    )
    async def load_operating_context(_args: dict[str, Any]) -> dict[str, Any]:
        return _json_result(context_overview(await asyncio.to_thread(bridge.load_context)))

    @tool(
        "load_creative_context",
        "Load a bounded section inventory of the DUFYND creative knowledge graph.",
        {},
    )
    async def load_creative_context(_args: dict[str, Any]) -> dict[str, Any]:
        return _json_result(context_overview(await asyncio.to_thread(bridge.load_creative_context)))

    @tool(
        "load_context_page",
        "Read bounded, lossless JSON text pages from a creative or operating context section. "
        "Use section paths from the inventory and follow next_offset until null.",
        {
            "type": "object",
            "properties": {
                "context": {"type": "string", "enum": ["creative", "operating"]},
                "section": {"type": "string"},
                "offset": {"type": "integer", "minimum": 0},
            },
            "required": ["context", "section"],
        },
    )
    async def load_context_page(args: dict[str, Any]) -> dict[str, Any]:
        loaders = {"creative": bridge.load_creative_context, "operating": bridge.load_context}
        if args["context"] not in loaders:
            raise ValueError("Context must be creative or operating")
        payload = await asyncio.to_thread(loaders[args["context"]])
        metadata, fragment = context_page(
            payload, section=args["section"], offset=int(args.get("offset", 0))
        )
        return _result(json.dumps(metadata, ensure_ascii=False) + "\n" + fragment)

    @tool(
        "load_creative_pattern_index",
        "Load a bounded compact index of existing DUFYND creative patterns for reuse-before-creation checks.",
        {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 200}},
        },
    )
    async def load_creative_pattern_index(args: dict[str, Any]) -> dict[str, Any]:
        return _json_result(
            await asyncio.to_thread(
                bridge.load_creative_pattern_index,
                limit=int(args.get("limit", 100)),
            )
        )

    @tool(
        "load_autonomy_queue",
        "Load safe work, human-input gates, external waits and approval-required DUFYND work.",
        {},
    )
    async def load_autonomy_queue(_args: dict[str, Any]) -> dict[str, Any]:
        return _json_result(await asyncio.to_thread(bridge.load_autonomy_queue))

    @tool(
        "load_experiment_rubric",
        "Load the shared DUFYND scoring rubric and hard-fail thresholds.",
        {},
    )
    async def load_experiment_rubric(_args: dict[str, Any]) -> dict[str, Any]:
        return _json_result(await asyncio.to_thread(bridge.load_experiment_rubric))

    @tool(
        "load_pending_decisions",
        "Load operator decisions that Jarvis must not make autonomously.",
        {},
    )
    async def load_pending_decisions(_args: dict[str, Any]) -> dict[str, Any]:
        return _json_result(await asyncio.to_thread(bridge.load_pending_decisions))

    @tool(
        "load_runtime_health",
        "Load Jarvis inbox health, learning counts, gates and current autonomy boundary.",
        {},
    )
    async def load_runtime_health(_args: dict[str, Any]) -> dict[str, Any]:
        return _json_result(await asyncio.to_thread(bridge.load_health))

    @tool(
        "record_creative_pattern",
        "Create one genuinely new reusable DUFYND creative pattern.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "role": {"type": "string"},
                "description": {"type": "string"},
                "mechanism": {"type": "string"},
                "strengths": {"type": "array", "items": {"type": "string"}},
                "risks": {"type": "array", "items": {"type": "string"}},
                "best_for": {"type": "array", "items": {"type": "string"}},
                "generation_guidance": {"type": "object"},
                "pattern_id": {"type": "string"},
            },
            "required": ["name", "role", "description", "mechanism", "pattern_id"],
        },
    )
    async def record_creative_pattern(args: dict[str, Any]) -> dict[str, Any]:
        pattern_id = await asyncio.to_thread(
            bridge.record_creative_pattern,
            name=args["name"],
            role=args["role"],
            description=args["description"],
            mechanism=args["mechanism"],
            strengths=args.get("strengths"),
            risks=args.get("risks"),
            best_for=args.get("best_for"),
            generation_guidance=args.get("generation_guidance"),
            pattern_id=_require_runtime_id(args["pattern_id"], "jarvis_pattern_"),
        )
        return _json_result({"pattern_id": pattern_id})

    @tool(
        "link_reference_pattern",
        "Link an existing DUFYND reference to a reusable pattern with evidence confidence.",
        {
            "type": "object",
            "properties": {
                "reference_id": {"type": "string"},
                "pattern_id": {"type": "string"},
                "confidence": {"type": "number"},
                "notes": {"type": "string"},
            },
            "required": ["reference_id", "pattern_id", "confidence"],
        },
    )
    async def link_reference_pattern(args: dict[str, Any]) -> dict[str, Any]:
        await asyncio.to_thread(
            bridge.link_reference_pattern,
            reference_id=args["reference_id"],
            pattern_id=args["pattern_id"],
            confidence=float(args["confidence"]),
            notes=args.get("notes"),
        )
        return _json_result({"linked": True})

    @tool(
        "record_content_idea",
        "Store one original DUFYND content concept. Avoid duplicates.",
        {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "concept": {"type": "string"},
                "hook": {"type": "string"},
                "format_id": {"type": "string"},
                "fragrance": {"type": "string"},
                "sequence": {"type": "array", "items": {"type": "string"}},
                "model_candidates": {"type": "array", "items": {"type": "string"}},
                "priority": {"type": "integer"},
                "objective": {"type": "string"},
                "target_platforms": {"type": "array", "items": {"type": "string"}},
                "asset_requirements": {"type": "array", "items": {"type": "string"}},
                "affiliate_role": {"type": "string"},
                "evaluation_metrics": {"type": "array", "items": {"type": "string"}},
                "risk_notes": {"type": "array", "items": {"type": "string"}},
                "hook_template_ids": {"type": "array", "items": {"type": "string"}},
                "idea_id": {"type": "string"},
            },
            "required": ["title", "concept", "hook", "idea_id"],
        },
    )
    async def record_content_idea(args: dict[str, Any]) -> dict[str, Any]:
        idea_id = await asyncio.to_thread(
            bridge.record_content_idea,
            title=args["title"],
            concept=args["concept"],
            hook=args["hook"],
            format_id=args.get("format_id"),
            fragrance=args.get("fragrance"),
            sequence=args.get("sequence"),
            model_candidates=args.get("model_candidates"),
            priority=int(args.get("priority", 50)),
            source="jarvis_runtime",
            objective=args.get("objective"),
            target_platforms=args.get("target_platforms"),
            asset_requirements=args.get("asset_requirements"),
            affiliate_role=args.get("affiliate_role"),
            evaluation_metrics=args.get("evaluation_metrics"),
            risk_notes=args.get("risk_notes"),
            hook_template_ids=args.get("hook_template_ids"),
            idea_id=_require_runtime_id(args["idea_id"], "jarvis_idea_"),
        )
        return _json_result({"idea_id": idea_id})

    @tool(
        "link_idea_pattern",
        "Link a Jarvis-created DUFYND idea to an existing reusable creative pattern.",
        {
            "type": "object",
            "properties": {
                "idea_id": {"type": "string"},
                "pattern_id": {"type": "string"},
                "role": {"type": "string"},
                "position": {"type": "integer"},
                "notes": {"type": "string"},
            },
            "required": ["idea_id", "pattern_id", "role"],
        },
    )
    async def link_idea_pattern(args: dict[str, Any]) -> dict[str, Any]:
        await asyncio.to_thread(
            bridge.link_idea_pattern,
            idea_id=_require_runtime_id(args["idea_id"], "jarvis_idea_"),
            pattern_id=args["pattern_id"],
            role=args["role"],
            position=int(args.get("position", 1)),
            notes=args.get("notes"),
        )
        return _json_result({"linked": True})

    @tool(
        "record_lesson",
        "Store one durable DUFYND lesson supported by evidence.",
        {
            "type": "object",
            "properties": {
                "domain": {"type": "string"},
                "lesson": {"type": "string"},
                "evidence": {"type": "string"},
                "action_rule": {"type": "string"},
                "confidence": {"type": "number"},
                "lesson_id": {"type": "string"},
            },
            "required": [
                "domain",
                "lesson",
                "evidence",
                "action_rule",
                "confidence",
                "lesson_id",
            ],
        },
    )
    async def record_lesson(args: dict[str, Any]) -> dict[str, Any]:
        lesson_id = await asyncio.to_thread(
            bridge.record_lesson,
            domain=args["domain"],
            lesson=args["lesson"],
            evidence=args["evidence"],
            action_rule=args["action_rule"],
            confidence=float(args["confidence"]),
            lesson_id=_require_runtime_id(args["lesson_id"], "jarvis_lesson_"),
        )
        return _json_result({"lesson_id": lesson_id})

    @tool(
        "record_knowledge_event",
        "Record a concise internal DUFYND learning/change event.",
        {
            "type": "object",
            "properties": {
                "event_type": {"type": "string"},
                "source_type": {"type": "string"},
                "source_id": {"type": "string"},
                "payload": {"type": "object"},
            },
            "required": ["event_type", "source_type", "payload"],
        },
    )
    async def record_knowledge_event(args: dict[str, Any]) -> dict[str, Any]:
        await asyncio.to_thread(
            bridge.record_knowledge_event,
            event_type=args["event_type"],
            source_type=args["source_type"],
            source_id=args.get("source_id"),
            payload=args["payload"],
        )
        return _json_result({"recorded": True})

    return [
        load_operating_context,
        load_creative_context,
        load_creative_pattern_index,
        load_context_page,
        load_autonomy_queue,
        load_experiment_rubric,
        load_pending_decisions,
        load_runtime_health,
        record_creative_pattern,
        link_reference_pattern,
        record_content_idea,
        link_idea_pattern,
        record_lesson,
        record_knowledge_event,
    ]


def build_server(bridge: DufyndJarvisBridge) -> McpSdkServerConfig:
    return create_sdk_mcp_server(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        tools=build_tools(bridge),
    )


def allowed_tool_names() -> list[str]:
    names = (
        "load_operating_context",
        "load_creative_context",
        "load_creative_pattern_index",
        "load_context_page",
        "load_autonomy_queue",
        "load_experiment_rubric",
        "load_pending_decisions",
        "load_runtime_health",
        "record_creative_pattern",
        "link_reference_pattern",
        "record_content_idea",
        "link_idea_pattern",
        "record_lesson",
        "record_knowledge_event",
    )
    return [f"mcp__{SERVER_NAME}__{name}" for name in names]


def runtime_readiness() -> dict[str, Any]:
    active = os.getenv("DUFYND_JARVIS_ACTIVE") == "1"
    model = os.getenv("DUFYND_JARVIS_MODEL")
    credentials = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))
    supabase = bool(
        os.getenv("SUPABASE_URL")
        and (os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    )
    autonomous = os.getenv("DUFYND_JARVIS_AUTONOMOUS") == "1"
    return {
        "active": active,
        "autonomous": autonomous,
        "model_configured": bool(model),
        "model": model,
        "anthropic_credentials_configured": credentials,
        "supabase_configured": supabase,
        "max_turns": os.getenv("DUFYND_JARVIS_MAX_TURNS", "8"),
        "max_budget_usd": os.getenv("DUFYND_JARVIS_MAX_BUDGET_USD", "0.25"),
        "budget_id": os.getenv("DUFYND_JARVIS_BUDGET_ID"),
        "ready_for_model_execution": active and bool(model) and credentials and supabase,
        "ready_for_autonomous_cycle": (
            active and autonomous and bool(model) and credentials and supabase
        ),
    }


def _require_active_runtime() -> tuple[str, int, float]:
    readiness = runtime_readiness()
    if not readiness["active"]:
        raise RuntimeError(
            "DUFYND Jarvis active model execution is disabled. "
            "Set DUFYND_JARVIS_ACTIVE=1 only after operator approval."
        )
    if not readiness["model_configured"]:
        raise RuntimeError("DUFYND_JARVIS_MODEL is required for active model execution.")
    if not readiness["anthropic_credentials_configured"]:
        raise RuntimeError("Anthropic credentials are required for active model execution.")
    raw_turns = os.getenv("DUFYND_JARVIS_MAX_TURNS", "8")
    raw_budget = os.getenv("DUFYND_JARVIS_MAX_BUDGET_USD", "0.25")
    try:
        max_turns = int(raw_turns)
    except ValueError as error:
        raise RuntimeError("DUFYND_JARVIS_MAX_TURNS must be an integer.") from error
    try:
        max_budget_usd = float(raw_budget)
    except ValueError as error:
        raise RuntimeError("DUFYND_JARVIS_MAX_BUDGET_USD must be numeric.") from error
    if max_budget_usd <= 0:
        raise RuntimeError("DUFYND_JARVIS_MAX_BUDGET_USD must be greater than zero.")
    return (
        str(readiness["model"]),
        max(4, min(max_turns, 12)),
        min(max_budget_usd, 1.0),
    )


def _require_budget_window(bridge: DufyndJarvisBridge) -> tuple[str, dict[str, Any]]:
    budget_id = os.getenv("DUFYND_JARVIS_BUDGET_ID")
    if not budget_id:
        raise RuntimeError("DUFYND_JARVIS_BUDGET_ID is required for active model execution.")
    status = bridge.load_budget_status(budget_id)

    window = bridge.load_budget_window(budget_id)
    if not window:
        raise RuntimeError(f"DUFYND Jarvis budget window {budget_id} is missing.")
    decision_id = str(window.get("approved_decision_id") or "")
    if not decision_id:
        raise RuntimeError(
            f"DUFYND Jarvis budget window {budget_id} has no approved decision reference."
        )
    decision = bridge.load_human_decision(decision_id)
    approved = dict((decision or {}).get("decision") or {})
    if not decision or decision.get("status") != "approved" or not bool(approved.get("approved")):
        raise RuntimeError(
            f"DUFYND Jarvis budget window {budget_id} is not backed by an approved human decision."
        )

    try:
        window_max_runs = int(window["max_runs"])
        approved_max_runs = int(approved["max_runs"])
        window_cap_usd = float(window["cap_usd"])
        approved_cap_usd = float(approved["cap_usd"])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(
            f"DUFYND Jarvis budget window {budget_id} has incomplete approval limits."
        ) from error

    if window_max_runs > approved_max_runs or window_cap_usd > approved_cap_usd:
        raise RuntimeError(
            "DUFYND Jarvis budget window exceeds its approved human limits: "
            f"window(max_runs={window_max_runs}, cap_usd={window_cap_usd}) vs "
            f"approved(max_runs={approved_max_runs}, cap_usd={approved_cap_usd})."
        )

    try:
        approved_per_run_cap_usd = float(approved["per_run_cap_usd"])
        configured_per_run_cap_usd = float(os.getenv("DUFYND_JARVIS_MAX_BUDGET_USD", "0.25"))
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(
            f"DUFYND Jarvis budget window {budget_id} has incomplete per-run approval limits."
        ) from error
    if configured_per_run_cap_usd > approved_per_run_cap_usd:
        raise RuntimeError(
            "DUFYND Jarvis configured per-run budget exceeds its approved human limit: "
            f"configured={configured_per_run_cap_usd} vs approved={approved_per_run_cap_usd}."
        )

    if not status.get("can_run"):
        raise RuntimeError(
            "DUFYND Jarvis budget window does not permit another run: "
            + json.dumps(status, ensure_ascii=False, default=str)
        )

    try:
        remaining_usd = float(status["remaining_usd"])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(
            f"DUFYND Jarvis budget window {budget_id} is missing a reliable remaining_usd."
        ) from error

    effective_per_run_cap_usd = min(
        configured_per_run_cap_usd,
        approved_per_run_cap_usd,
        remaining_usd,
    )
    try:
        sdk_budget_usd = _sdk_budget_limit(effective_per_run_cap_usd)
    except RuntimeError as error:
        raise RuntimeError(
            "DUFYND Jarvis budget gate: remaining total budget is too small "
            "for another safely bounded model turn."
        ) from error

    configured_model = os.getenv("DUFYND_JARVIS_MODEL")
    budget_model = status.get("model")
    if budget_model and configured_model and budget_model != configured_model:
        raise RuntimeError(
            f"Jarvis budget window requires model {budget_model}, not {configured_model}."
        )

    status = dict(status)
    status["effective_per_run_cap_usd"] = round(effective_per_run_cap_usd, 6)
    status["sdk_budget_usd"] = sdk_budget_usd
    return budget_id, status


def _require_autonomous_mode() -> None:
    readiness = runtime_readiness()
    if not readiness["autonomous"]:
        raise RuntimeError(
            "DUFYND Jarvis autonomous cycle is disabled. "
            "Set DUFYND_JARVIS_AUTONOMOUS=1 only for an operator-approved budget session."
        )
    _require_active_runtime()


def _require_autonomous_session(
    bridge: DufyndJarvisBridge,
) -> tuple[str, dict[str, Any]]:
    _require_autonomous_mode()
    return _require_budget_window(bridge)


def _sdk_budget_limit(approved_per_run_cap_usd: float) -> float:
    """Leave headroom because the SDK can finish a turn slightly above its stop threshold."""
    bounded = round(float(approved_per_run_cap_usd) * 0.8, 4)
    if bounded < 0.01:
        raise RuntimeError("Effective per-run budget is below the safe SDK minimum.")
    return bounded


def make_options(bridge: DufyndJarvisBridge) -> ClaudeAgentOptions:
    model, max_turns, _configured_per_run_cap_usd = _require_active_runtime()
    _, budget = _require_budget_window(bridge)
    sdk_budget_usd = float(budget["sdk_budget_usd"])
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={SERVER_NAME: build_server(bridge)},
        allowed_tools=allowed_tool_names(),
        tools=[],
        cwd=REPO_ROOT,
        env={"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1"},
        model=model,
        max_turns=max_turns,
        max_budget_usd=sdk_budget_usd,
        permission_mode="dontAsk",
    )


SAFE_WORKER_SYSTEM_PROMPT = (
    SYSTEM_PROMPT
    + """
You are running as the DUFYND safe research worker.
You may inspect repository files and research the public web, but you must not write
or edit repository files, run shell commands, publish content, spend money, change
live catalog or affiliate routing, accept contracts, send outbound messages, change
credentials, or merge/push code. Treat external claims as evidence candidates until
verified. Your output should be concise, evidence-led, and useful for the next
controlled DUFYND step.
"""
)


def make_safe_worker_options(bridge: DufyndJarvisBridge) -> ClaudeAgentOptions:
    model, max_turns, _configured_per_run_cap_usd = _require_active_runtime()
    _, budget = _require_budget_window(bridge)
    sdk_budget_usd = float(budget["sdk_budget_usd"])
    builtins = ["Read", "Grep", "Glob", "WebSearch", "WebFetch"]
    return ClaudeAgentOptions(
        system_prompt=SAFE_WORKER_SYSTEM_PROMPT,
        mcp_servers={SERVER_NAME: build_server(bridge)},
        allowed_tools=[*allowed_tool_names(), *builtins],
        disallowed_tools=["Bash", "Write", "Edit", "Task"],
        cwd=REPO_ROOT,
        env={"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1"},
        model=model,
        max_turns=max_turns,
        max_budget_usd=sdk_budget_usd,
        permission_mode="dontAsk",
    )


BRANCH_WORKER_SYSTEM_PROMPT = (
    SYSTEM_PROMPT
    + """
You are running as the DUFYND isolated branch-preparation worker.
You may read and edit the checked-out repository only to prepare a reversible patch
for a current safe engineering task. You must not run shell commands, publish
content, spend money, change credentials, modify live catalog/affiliate data, send
outbound messages, accept contracts, push, merge, or claim deployment. Avoid
.github workflows, Supabase migrations, secrets, lockfiles, dependency manifests,
and examples/retail/data. Keep changes minimal and add/update tests when needed.
A deterministic workflow will validate changed paths and run tests after your turn.
"""
)


def make_branch_worker_options(bridge: DufyndJarvisBridge) -> ClaudeAgentOptions:
    model, max_turns, _configured_per_run_cap_usd = _require_active_runtime()
    _, budget = _require_budget_window(bridge)
    sdk_budget_usd = float(budget["sdk_budget_usd"])
    builtins = ["Read", "Grep", "Glob", "Write", "Edit"]
    return ClaudeAgentOptions(
        system_prompt=BRANCH_WORKER_SYSTEM_PROMPT,
        mcp_servers={SERVER_NAME: build_server(bridge)},
        allowed_tools=[*allowed_tool_names(), *builtins],
        disallowed_tools=["Bash", "Task", "WebSearch", "WebFetch"],
        cwd=REPO_ROOT,
        env={"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1"},
        model=model,
        max_turns=max_turns,
        max_budget_usd=sdk_budget_usd,
        permission_mode="acceptEdits",
    )


def event_prompt(event: dict[str, Any]) -> str:
    return (
        "Process this internal DUFYND Jarvis event. Follow the system rules, "
        "load the context you need, write only durable internal learning, and do "
        "not manufacture changes when the knowledge base is already coherent.\n\n"
        + json.dumps(event, ensure_ascii=False, default=str)
    )


async def run_prompt(
    prompt: str,
    bridge: DufyndJarvisBridge,
    *,
    budget_id: str | None = None,
) -> tuple[str, float | None, str]:
    resolved_budget_id = budget_id
    if resolved_budget_id is None:
        resolved_budget_id, _ = await asyncio.to_thread(_require_budget_window, bridge)
    require_bounded_provider_execution()
    options = make_options(bridge)
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        result = await collect_turn(client)
    if result.is_error:
        detail = "; ".join(result.tool_errors) or result.text or "Jarvis SDK turn failed"
        raise JarvisTurnError(
            detail,
            cost_usd=result.cost_usd,
            budget_id=resolved_budget_id,
        )
    return result.text.strip(), result.cost_usd, resolved_budget_id


def _deterministic_event_summary(event: dict[str, Any]) -> str | None:
    if str(event.get("event_type") or "") != "affiliate_partner_changed":
        return None
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return None

    readiness_keys = (
        "feed_ready_before",
        "feed_ready_after",
        "tracking_ready_before",
        "tracking_ready_after",
    )
    if any(key not in payload for key in readiness_keys):
        return None
    if payload["feed_ready_before"] != payload["feed_ready_after"]:
        return None
    if payload["tracking_ready_before"] != payload["tracking_ready_after"]:
        return None

    merchant = str(
        payload.get("merchant_name")
        or payload.get("merchant_id")
        or event.get("source_id")
        or "affiliate partner"
    )
    before = str(payload.get("status_before") or "unknown")
    after = str(payload.get("status_after") or "unknown")
    return (
        f"Deterministic affiliate status update for {merchant}: {before} -> {after}. "
        "Feed/tracking readiness did not change, so no model reasoning is required."
    )


async def _process_next_outcome(bridge: DufyndJarvisBridge) -> tuple[int, bool]:
    health = await asyncio.to_thread(bridge.load_health)
    if int((health.get("inbox") or {}).get("pending") or 0) == 0:
        print("DUFYND Jarvis inbox: no pending event.")
        return 0, False

    event = await asyncio.to_thread(bridge.claim_next_inbox_event)
    if event is None:
        print("DUFYND Jarvis inbox: no pending event.")
        return 0, False

    inbox_id = int(event["inbox_id"])
    attempts = int(event.get("attempts") or 0)
    budget_id: str | None = None

    try:
        deterministic_summary = _deterministic_event_summary(event)
        if deterministic_summary is not None:
            await asyncio.to_thread(
                bridge.record_run,
                run_type=f"inbox_deterministic:{event.get('event_type', 'unknown')}",
                input_summary=json.dumps(event, ensure_ascii=False, default=str)[:4000],
                output_summary=deterministic_summary,
                decisions=[
                    {
                        "inbox_id": inbox_id,
                        "event_type": event.get("event_type"),
                        "cost_usd": 0,
                        "runtime": "dufynd_jarvis_deterministic_v1",
                        "reason": "affiliate_status_only_no_readiness_change",
                    }
                ],
                human_approval_required=False,
                agent_name="jarvis",
            )
            await asyncio.to_thread(
                bridge.complete_inbox_event,
                inbox_id=inbox_id,
                status="done",
            )
            print(
                "DUFYND Jarvis deterministically processed "
                f"inbox_id={inbox_id} event={event.get('event_type')} cost_usd=0"
            )
            return 0, False

        budget_id, _ = await asyncio.to_thread(_require_budget_window, bridge)
        text, cost_usd, _ = await run_prompt(
            event_prompt(event),
            bridge,
            budget_id=budget_id,
        )
        await asyncio.to_thread(
            bridge.record_run,
            run_type=f"inbox:{event.get('event_type', 'unknown')}",
            input_summary=json.dumps(event, ensure_ascii=False, default=str)[:4000],
            output_summary=text[:8000] or "(Jarvis produced no prose output)",
            decisions=[
                {
                    "inbox_id": inbox_id,
                    "event_type": event.get("event_type"),
                    "cost_usd": cost_usd,
                    "budget_id": budget_id,
                    "runtime": "dufynd_jarvis_v0_1",
                }
            ],
            human_approval_required=False,
            agent_name="jarvis",
        )
        await asyncio.to_thread(
            bridge.complete_inbox_event,
            inbox_id=inbox_id,
            status="done",
        )
        print(
            "DUFYND Jarvis processed "
            f"inbox_id={inbox_id} event={event.get('event_type')} "
            f"cost_usd={cost_usd if cost_usd is not None else 'unknown'}"
        )
        if text:
            print(text)
        return 0, True
    except asyncio.CancelledError:
        with suppress(Exception):
            await asyncio.wait_for(
                asyncio.to_thread(
                    bridge.complete_inbox_event,
                    inbox_id=inbox_id,
                    status="failed",
                    error=(
                        "Jarvis inbox processing cancelled after claim; "
                        "provider cost may be unknown; no automatic retry."
                    ),
                ),
                timeout=3.0,
            )
        raise
    except RuntimeError as error:
        if not isinstance(error, JarvisTurnError):
            await asyncio.to_thread(
                bridge.complete_inbox_event,
                inbox_id=inbox_id,
                status="pending",
                error=str(error)[:4000],
            )
            print(
                f"DUFYND Jarvis event {inbox_id} returned to pending at runtime/budget gate: {error}",
                file=sys.stderr,
            )
            raise
        if error.cost_usd is not None:
            await asyncio.to_thread(
                bridge.record_run,
                run_type=f"inbox_failed:{event.get('event_type', 'unknown')}",
                input_summary=json.dumps(event, ensure_ascii=False, default=str)[:4000],
                output_summary=str(error)[:8000],
                decisions=[
                    {
                        "inbox_id": inbox_id,
                        "event_type": event.get("event_type"),
                        "cost_usd": error.cost_usd,
                        "budget_id": error.budget_id or budget_id,
                        "runtime": "dufynd_jarvis_v0_1",
                        "failed_model_turn": True,
                    }
                ],
                human_approval_required=False,
                agent_name="jarvis",
            )
        provider_cost_unknown = error.cost_usd is None
        retry = attempts < 3 and not provider_cost_unknown
        failure_note = str(error)
        if provider_cost_unknown:
            failure_note = f"{failure_note} | provider cost unknown; no automatic retry."
        await asyncio.to_thread(
            bridge.complete_inbox_event,
            inbox_id=inbox_id,
            status="pending" if retry else "failed",
            error=failure_note[:4000],
        )
        print(
            f"DUFYND Jarvis event {inbox_id} failed; "
            f"{'queued for retry' if retry else 'marked failed'}: {failure_note}",
            file=sys.stderr,
        )
        return 1, True
    except Exception as error:
        provider_cost_unknown = budget_id is not None
        retry = attempts < 3 and not provider_cost_unknown
        failure_note = str(error)
        if provider_cost_unknown:
            failure_note = f"{failure_note} | provider cost unknown; no automatic retry."
        await asyncio.to_thread(
            bridge.complete_inbox_event,
            inbox_id=inbox_id,
            status="pending" if retry else "failed",
            error=failure_note[:4000],
        )
        print(
            f"DUFYND Jarvis event {inbox_id} failed; "
            f"{'queued for retry' if retry else 'marked failed'}: {failure_note}",
            file=sys.stderr,
        )
        return 1, budget_id is not None


async def process_next(bridge: DufyndJarvisBridge) -> int:
    result, _used_model = await _process_next_outcome(bridge)
    return result


def safe_task_prompt(task: dict[str, Any]) -> str:
    domain = str(task.get("domain") or "research")
    role_guidance = {
        "commerce": (
            "Act as the DUFYND Commerce Worker: verify product, merchant, affiliate, "
            "price/feed and catalog evidence without activating live routing."
        ),
        "content": (
            "Act as the DUFYND Content Worker: prepare ideas, storyboards, prompts, "
            "shot plans and review material without publishing."
        ),
        "research": (
            "Act as the DUFYND Research Worker: gather and validate evidence from "
            "current internal context and public sources."
        ),
    }.get(
        domain,
        "Act as the DUFYND Research Worker for this bounded internal task.",
    )
    return (
        f"{role_guidance} "
        "First load the current autonomy queue and runtime health. Prefer bounded "
        "indexes and targeted repository reads; load the comprehensive operating "
        "context only when specifically necessary. Use repository read/search tools "
        "and public web research when useful. Do not perform any "
        "high-impact action. Produce evidence, blockers, and the next safe step; do "
        "not claim publication, licensing rights, stock, price, or identity without "
        "verification. End your response with exactly one machine-readable outcome "
        "line: DUFYND_TASK_STATE: done, DUFYND_TASK_STATE: waiting_human_input, "
        "DUFYND_TASK_STATE: waiting_external, DUFYND_TASK_STATE: blocked, or "
        "DUFYND_TASK_STATE: in_progress. Use done only when the requested safe task "
        "is fully resolved for the current repository fingerprint. Use "
        "waiting_human_input when the next action is YELLOW/owner review, "
        "waiting_external for an external dependency, blocked for a genuine "
        "task-local blocker, and in_progress when useful work remains. "
        "A human gate additionally requires a line DUFYND_BLOCK_REASON: "
        "owner_decision, spend_approval, publication_approval, or contract_approval. "
        "Budget exhaustion, session limits, tool timeouts, unread files and technical "
        "research are autonomous continuation reasons, never human gates.\n\n"
        + json.dumps(task, ensure_ascii=False, default=str)
    )


SAFE_TASK_STATES = {
    "done",
    "waiting_human_input",
    "waiting_external",
    "blocked",
    "in_progress",
}


def _is_green_autonomy_task(
    task: object,
    *,
    domain: str | None = None,
) -> bool:
    """Return whether a queue item is safe for autonomous Jarvis execution.

    The database queue is the authority for readiness. Task identifiers are not
    an authorization boundary: manually queued Jarvis work must not be ignored
    merely because its id does not use the legacy repo_current_ prefix.
    """
    if not isinstance(task, dict):
        return False
    if bool(task.get("requires_human_approval")):
        return False
    action_type = str(task.get("approval_action_type") or "auto_allowed")
    if action_type != "auto_allowed":
        return False
    return domain is None or str(task.get("domain") or "") == domain


def _extract_safe_task_state(text: str) -> str | None:
    for line in reversed(text.splitlines()):
        normalized = line.strip()
        if not normalized.startswith("DUFYND_TASK_STATE:"):
            continue
        state = normalized.split(":", 1)[1].strip()
        return state if state in SAFE_TASK_STATES else None
    return None


def require_bounded_provider_execution() -> None:
    """SDK max_budget_usd is a post-call stop threshold, not a hard cost bound.

    Until a per-call token/pricing bound and atomic reservation adapter is present,
    starting this provider would violate the approved cap. No env switch bypasses
    this boundary. Deterministic event/health work never calls this function.
    """
    raise RuntimeError("Jarvis budget gate: unbounded_provider_cost; paid SDK execution parked")


def leased_worker(function):
    @wraps(function)
    async def controlled(bridge: DufyndJarvisBridge, *, task_id: str | None = None) -> int:
        queue = await asyncio.to_thread(bridge.load_autonomy_queue)
        candidates = [
            t
            for t in queue.get("safe_to_execute", [])
            if _is_green_autonomy_task(t)
            and (t.get("domain") == "engineering") == (function.__name__ == "process_branch_task")
            and (task_id is None or t.get("task_id") == task_id)
        ]
        if not candidates:
            return await function(bridge, task_id=task_id)
        selected = candidates[0]
        task_id = str(selected["task_id"])
        # Gate before acquiring any worker lease or starting a paid provider.
        require_bounded_provider_execution()
        claimed = await asyncio.to_thread(bridge.claim_worker, task_id, "jarvis-runtime-v2")
        if claimed is None:
            return 0
        reason = "retryable_error"
        result = 1

        async def pulse():
            while True:
                await asyncio.sleep(45)
                await asyncio.to_thread(bridge.update_worker, task_id, "heartbeat")

        heartbeat = asyncio.create_task(pulse())
        work = asyncio.create_task(function(bridge, task_id=task_id))
        try:
            finished, _ = await asyncio.wait({heartbeat, work}, return_when=asyncio.FIRST_COMPLETED)
            if heartbeat in finished:
                heartbeat.result()  # A lease failure cancels the worker below.
                raise RuntimeError("Worker heartbeat ended unexpectedly")
            result = work.result()
            reason = "worker_result"
            return result
        finally:
            work.cancel()
            heartbeat.cancel()
            with suppress(Exception, asyncio.CancelledError):
                await work
            with suppress(asyncio.CancelledError, RuntimeError):
                await heartbeat
            try:
                current = await asyncio.to_thread(bridge.load_autonomy_task, task_id) or claimed
                evidence = str(current.get("evidence") or "")
                marker = _extract_safe_task_state(evidence)
                state = "queued"
                if result == 0 and function.__name__ == "process_branch_task":
                    state, reason = "waiting_external", "verification_pending"
                    evidence += "\nDeterministic QA/PR verification pending; no further model work required."
                elif result == 0 and marker == "done":
                    await asyncio.to_thread(
                        bridge.update_worker, task_id, "verifying", evidence=evidence
                    )
                    # Model completion is evidence to review, not proof of done.
                    state, reason = "waiting_external", "verification_pending"
                    evidence += "\nSupervisor verification required before terminal completion."
                elif (
                    result == 0
                    and marker == "waiting_human_input"
                    and human_gate_allowed(selected, evidence)
                ):
                    state = "waiting_human_input"
                    reason = next(
                        (r for r in HUMAN_REASONS if f"DUFYND_BLOCK_REASON: {r}" in evidence),
                        "owner_decision",
                    )
                elif result == 0 and marker == "waiting_external":
                    state, reason = "waiting_external", "external_dependency"
                elif result != 0:
                    state = "failed_retryable"
                evidence += f"\nDUFYND_TASK_STATE: {'in_progress' if state in {'queued', 'failed_retryable'} else state}"
                await asyncio.to_thread(
                    bridge.update_worker, task_id, state, evidence=evidence, reason=reason
                )
            finally:
                bridge.worker_tokens.pop(task_id, None)

    return controlled


@leased_worker
async def process_safe_task(
    bridge: DufyndJarvisBridge,
    *,
    task_id: str | None = None,
) -> int:
    queue = await asyncio.to_thread(bridge.load_autonomy_queue)
    safe_tasks = [
        task
        for task in (queue.get("safe_to_execute") or [])
        if _is_green_autonomy_task(task) and str(task.get("domain") or "") != "engineering"
    ]
    if task_id is not None:
        safe_tasks = [task for task in safe_tasks if str(task.get("task_id") or "") == task_id]
    if not safe_tasks:
        message = (
            f"DUFYND Jarvis safe worker: requested task {task_id} is not safely executable."
            if task_id is not None
            else "DUFYND Jarvis safe worker: no GREEN safe task."
        )
        print(message)
        return 0

    task = safe_tasks[0]
    task_id = str(task["task_id"])
    budget_id, _ = await asyncio.to_thread(_require_budget_window, bridge)

    await asyncio.to_thread(
        bridge.update_autonomy_task_progress,
        task_id=task_id,
        status="in_progress",
        evidence=(
            "Safe worker claimed current repo-derived task. "
            "No terminal completion is recorded automatically."
        ),
    )

    try:
        require_bounded_provider_execution()
        options = make_safe_worker_options(bridge)
        async with ClaudeSDKClient(options=options) as client:
            await client.query(safe_task_prompt(task))
            result = await collect_turn(client)

        text = result.text.strip()
        worker_state = _extract_safe_task_state(text)
        if result.is_error and worker_state is None:
            detail = "; ".join(result.tool_errors) or result.text or "Safe worker failed"
            await asyncio.to_thread(
                bridge.record_run,
                run_type=f"safe_task_failed:{task_id}",
                input_summary=json.dumps(task, ensure_ascii=False, default=str)[:4000],
                output_summary=detail[:8000],
                decisions=[
                    {
                        "task_id": task_id,
                        "cost_usd": result.cost_usd,
                        "budget_id": budget_id,
                        "runtime": "dufynd_jarvis_safe_worker_v1",
                        "worker_role": str(task.get("domain") or "research"),
                        "failed_model_turn": True,
                    }
                ],
                human_approval_required=False,
                agent_name="jarvis",
            )
            raise RuntimeError(detail)

        if worker_state == "waiting_human_input" and not human_gate_allowed(task, text):
            worker_state = "in_progress"
            text += "\nSupervisor V2: unclassified human gate; autonomous continuation required."
        progress_status = (
            worker_state
            if worker_state in {"waiting_human_input", "waiting_external", "blocked"}
            else "in_progress"
        )
        await asyncio.to_thread(
            bridge.update_autonomy_task_progress,
            task_id=task_id,
            status=progress_status,
            evidence=text[:12000] or "Safe worker completed without prose evidence.",
        )
        await asyncio.to_thread(
            bridge.record_run,
            run_type=(
                f"safe_task_soft_error:{task_id}" if result.is_error else f"safe_task:{task_id}"
            ),
            input_summary=json.dumps(task, ensure_ascii=False, default=str)[:4000],
            output_summary=text[:8000] or "(safe worker produced no prose output)",
            decisions=[
                {
                    "task_id": task_id,
                    "cost_usd": result.cost_usd,
                    "budget_id": budget_id,
                    "runtime": "dufynd_jarvis_safe_worker_v1",
                    "worker_role": str(task.get("domain") or "research"),
                    "terminal_completion_recorded": False,
                    "worker_state": worker_state,
                    "sdk_reported_error": bool(result.is_error),
                }
            ],
            human_approval_required=False,
            agent_name="jarvis",
        )
        print(
            "DUFYND Jarvis safe worker processed "
            f"task_id={task_id} cost_usd="
            f"{result.cost_usd if result.cost_usd is not None else 'unknown'}"
        )
        if text:
            print(text)
        return 0
    except Exception as error:
        await asyncio.to_thread(
            bridge.update_autonomy_task_progress,
            task_id=task_id,
            status="blocked",
            evidence=f"Safe worker failed without terminal task completion: {error}"[:12000],
        )
        print(f"DUFYND Jarvis safe worker failed for {task_id}: {error}", file=sys.stderr)
        return 1


def branch_task_prompt(task: dict[str, Any]) -> str:
    return (
        "Act as the DUFYND Tech Worker. Prepare a minimal tested-code patch for "
        "this DUFYND engineering task. "
        "Only edit repository files that are necessary for the task. Do not touch "
        "protected operational data or workflows. Do not run commands yourself; "
        "the deterministic workflow will validate paths and run checks after your "
        "turn. Do not mark the task complete.\n\n"
        + json.dumps(task, ensure_ascii=False, default=str)
    )


@leased_worker
async def process_branch_task(
    bridge: DufyndJarvisBridge,
    *,
    task_id: str | None = None,
) -> int:
    queue = await asyncio.to_thread(bridge.load_autonomy_queue)
    tasks = [
        task
        for task in (queue.get("safe_to_execute") or [])
        if _is_green_autonomy_task(task, domain="engineering")
    ]
    if task_id is not None:
        tasks = [task for task in tasks if str(task.get("task_id") or "") == task_id]
    if not tasks:
        message = (
            f"DUFYND Jarvis branch worker: requested task {task_id} is not safely executable."
            if task_id is not None
            else "DUFYND Jarvis branch worker: no GREEN safe engineering task."
        )
        print(message)
        return 0

    task = tasks[0]
    task_id = str(task["task_id"])
    budget_id, _ = await asyncio.to_thread(_require_budget_window, bridge)

    await asyncio.to_thread(
        bridge.update_autonomy_task_progress,
        task_id=task_id,
        status="in_progress",
        evidence=(
            "Branch worker claimed current safe engineering task for isolated "
            "patch preparation. No merge or terminal completion is recorded."
        ),
    )

    try:
        require_bounded_provider_execution()
        options = make_branch_worker_options(bridge)
        async with ClaudeSDKClient(options=options) as client:
            await client.query(branch_task_prompt(task))
            result = await collect_turn(client)
        if result.is_error:
            detail = "; ".join(result.tool_errors) or result.text or "Branch worker failed"
            await asyncio.to_thread(
                bridge.record_run,
                run_type=f"branch_task_failed:{task_id}",
                input_summary=json.dumps(task, ensure_ascii=False, default=str)[:4000],
                output_summary=detail[:8000],
                decisions=[
                    {
                        "task_id": task_id,
                        "cost_usd": result.cost_usd,
                        "budget_id": budget_id,
                        "runtime": "dufynd_jarvis_branch_worker_v1",
                        "worker_role": "engineering",
                        "failed_model_turn": True,
                    }
                ],
                human_approval_required=False,
                agent_name="jarvis",
            )
            raise RuntimeError(detail)

        text = result.text.strip()
        await asyncio.to_thread(
            bridge.update_autonomy_task_progress,
            task_id=task_id,
            status="in_progress",
            evidence=(
                text[:12000] or "Branch worker prepared a local patch without terminal completion."
            ),
        )
        await asyncio.to_thread(
            bridge.record_run,
            run_type=f"branch_task:{task_id}",
            input_summary=json.dumps(task, ensure_ascii=False, default=str)[:4000],
            output_summary=text[:8000] or "(branch worker produced no prose output)",
            decisions=[
                {
                    "task_id": task_id,
                    "cost_usd": result.cost_usd,
                    "budget_id": budget_id,
                    "runtime": "dufynd_jarvis_branch_worker_v1",
                    "worker_role": "engineering",
                    "push_performed": False,
                    "merge_performed": False,
                    "terminal_completion_recorded": False,
                }
            ],
            human_approval_required=False,
            agent_name="jarvis",
        )
        if text:
            print(text)
        return 0
    except Exception as error:
        await asyncio.to_thread(
            bridge.update_autonomy_task_progress,
            task_id=task_id,
            status="blocked",
            evidence=f"Branch worker failed without merge/completion: {error}"[:12000],
        )
        print(f"DUFYND Jarvis branch worker failed for {task_id}: {error}", file=sys.stderr)
        return 1


def _bounded_supervisor_max_events(value: int) -> int:
    return max(1, min(int(value), HARD_SUPERVISOR_MAX_EVENTS))


async def process_loop(
    bridge: DufyndJarvisBridge,
    *,
    max_events: int = DEFAULT_SUPERVISOR_MAX_EVENTS,
) -> int:
    model_limit = _bounded_supervisor_max_events(max_events)
    model_events = 0
    deterministic_events = 0
    total_events = 0
    stop_reason = "max_model_events_reached"

    while model_events < model_limit and total_events < HARD_SUPERVISOR_MAX_EVENTS:
        health = await asyncio.to_thread(bridge.load_health)
        pending = int((health.get("inbox") or {}).get("pending") or 0)
        if pending <= 0:
            stop_reason = "inbox_empty"
            break

        try:
            result, used_model = await _process_next_outcome(bridge)
        except RuntimeError as error:
            stop_reason = "runtime_or_budget_gate"
            print(f"DUFYND Jarvis supervisor stopped safely after {total_events} event(s): {error}")
            break

        if result != 0:
            print(
                "DUFYND Jarvis supervisor stopped after "
                f"{total_events} completed event(s) because the next event failed.",
                file=sys.stderr,
            )
            return result

        total_events += 1
        if used_model:
            model_events += 1
        else:
            deterministic_events += 1

    if total_events >= HARD_SUPERVISOR_MAX_EVENTS and model_events < model_limit:
        stop_reason = "hard_total_event_limit_reached"

    print(
        "DUFYND Jarvis supervisor summary | "
        f"processed={total_events} | model_events={model_events} | "
        f"deterministic_events={deterministic_events} | model_limit={model_limit} | "
        f"stop_reason={stop_reason}"
    )
    return 0


def _bounded_autonomous_max_events(value: int) -> int:
    return max(0, min(int(value), HARD_AUTONOMOUS_MAX_EVENTS))


async def process_autonomous_cycle(
    bridge: DufyndJarvisBridge,
    *,
    max_events: int = DEFAULT_AUTONOMOUS_MAX_EVENTS,
) -> int:
    _require_autonomous_session(bridge)
    event_limit = _bounded_autonomous_max_events(max_events)

    if event_limit:
        event_result = await process_loop(bridge, max_events=event_limit)
        if event_result != 0:
            return event_result

    health = await asyncio.to_thread(bridge.load_health)
    pending = int((health.get("inbox") or {}).get("pending") or 0)
    if pending > 0:
        print(
            "DUFYND Jarvis autonomous cycle: inbox backlog remains; safe-task execution deferred."
        )
        return 0

    queue = await asyncio.to_thread(bridge.load_autonomy_queue)
    safe_tasks = [
        task for task in (queue.get("safe_to_execute") or []) if _is_green_autonomy_task(task)
    ]

    if not safe_tasks:
        print(
            "DUFYND Jarvis autonomous cycle summary | "
            f"event_limit={event_limit} | worker=none | task_result=0"
        )
        return 0

    selected = safe_tasks[0]
    selected_domain = str(selected.get("domain") or "")
    if selected_domain == "engineering":
        worker = "branch_worker"
        task_result = await process_branch_task(bridge)
    else:
        worker = "safe_worker"
        task_result = await process_safe_task(bridge)

    print(
        "DUFYND Jarvis autonomous cycle summary | "
        f"event_limit={event_limit} | worker={worker} | task_result={task_result}"
    )
    return task_result


async def run_once(prompt: str, bridge: DufyndJarvisBridge) -> int:
    budget_id, _ = await asyncio.to_thread(_require_budget_window, bridge)
    try:
        text, cost_usd, _ = await run_prompt(prompt, bridge, budget_id=budget_id)
    except JarvisTurnError as error:
        if error.cost_usd is not None:
            await asyncio.to_thread(
                bridge.record_run,
                run_type="manual_internal_failed",
                input_summary=prompt[:4000],
                output_summary=str(error)[:8000],
                decisions=[
                    {
                        "cost_usd": error.cost_usd,
                        "budget_id": error.budget_id or budget_id,
                        "runtime": "dufynd_jarvis_v0_1",
                        "failed_model_turn": True,
                    }
                ],
                human_approval_required=False,
                agent_name="jarvis",
            )
        raise

    await asyncio.to_thread(
        bridge.record_run,
        run_type="manual_internal",
        input_summary=prompt[:4000],
        output_summary=text[:8000] or "(Jarvis produced no prose output)",
        decisions=[
            {
                "cost_usd": cost_usd,
                "budget_id": budget_id,
                "runtime": "dufynd_jarvis_v0_1",
            }
        ],
        human_approval_required=False,
        agent_name="jarvis",
    )
    if text:
        print(text)
    if cost_usd is not None:
        print(f"[Jarvis cost: USD {cost_usd:.4f}]")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="DUFYND Jarvis v0.1 internal Agent SDK runtime.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--readiness",
        action="store_true",
        help="report configuration readiness without invoking a model",
    )
    group.add_argument(
        "--process-next",
        action="store_true",
        help="claim and process one internal Jarvis inbox event",
    )
    group.add_argument(
        "--process-loop",
        action="store_true",
        help="process multiple queued Jarvis events until a safe stop condition",
    )
    group.add_argument(
        "--autonomous-cycle",
        action="store_true",
        help="run one bounded budget-gated Jarvis autonomous operating cycle",
    )
    group.add_argument(
        "--process-safe-task",
        action="store_true",
        help="research one current repo-derived safe autonomy task",
    )
    group.add_argument(
        "--process-branch-task",
        action="store_true",
        help="prepare one local patch for a safe repo-current engineering task",
    )
    group.add_argument(
        "--once",
        metavar="PROMPT",
        help="run one manual internal Jarvis task",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=DEFAULT_SUPERVISOR_MAX_EVENTS,
        help=(
            f"maximum events for --process-loop; values are clamped to {HARD_SUPERVISOR_MAX_EVENTS}"
        ),
    )
    parser.add_argument(
        "--autonomous-max-events",
        type=int,
        default=DEFAULT_AUTONOMOUS_MAX_EVENTS,
        help=(
            "maximum inbox events for --autonomous-cycle; values are clamped to "
            f"{HARD_AUTONOMOUS_MAX_EVENTS}"
        ),
    )
    args = parser.parse_args()

    if args.readiness:
        print(json.dumps(runtime_readiness(), ensure_ascii=False))
        return 0

    bridge = DufyndJarvisBridge()
    if args.autonomous_cycle:
        return asyncio.run(
            process_autonomous_cycle(
                bridge,
                max_events=args.autonomous_max_events,
            )
        )
    if args.process_branch_task:
        return asyncio.run(process_branch_task(bridge))
    if args.process_safe_task:
        return asyncio.run(process_safe_task(bridge))
    if args.process_loop:
        return asyncio.run(process_loop(bridge, max_events=args.max_events))
    if args.process_next:
        return asyncio.run(process_next(bridge))
    return asyncio.run(run_once(args.once, bridge))


if __name__ == "__main__":
    raise SystemExit(main())
