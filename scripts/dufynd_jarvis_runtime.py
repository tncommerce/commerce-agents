from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
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
SERVER_NAME = "dufynd_jarvis"
SERVER_VERSION = "0.1.0"

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
- load creative context
- inspect existing patterns and lessons
- identify the reusable mechanisms
- link the reference to existing patterns where possible
- create a new pattern only when truly distinct
- create at most three original DUFYND adaptations when they add value
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
        "Load the comprehensive internal DUFYND/Jarvis operating context.",
        {},
    )
    async def load_operating_context(_args: dict[str, Any]) -> dict[str, Any]:
        return _json_result(await asyncio.to_thread(bridge.load_context))

    @tool(
        "load_creative_context",
        "Load the DUFYND creative knowledge graph, board, references and learning state.",
        {},
    )
    async def load_creative_context(_args: dict[str, Any]) -> dict[str, Any]:
        return _json_result(await asyncio.to_thread(bridge.load_creative_context))

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
        load_autonomy_queue,
        load_experiment_rubric,
        load_pending_decisions,
        load_runtime_health,
        record_creative_pattern,
        link_reference_pattern,
        record_content_idea,
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
        "load_autonomy_queue",
        "load_experiment_rubric",
        "load_pending_decisions",
        "load_runtime_health",
        "record_creative_pattern",
        "link_reference_pattern",
        "record_content_idea",
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
    return {
        "active": active,
        "model_configured": bool(model),
        "model": model,
        "anthropic_credentials_configured": credentials,
        "supabase_configured": supabase,
        "max_turns": os.getenv("DUFYND_JARVIS_MAX_TURNS", "8"),
        "max_budget_usd": os.getenv("DUFYND_JARVIS_MAX_BUDGET_USD", "0.25"),
        "budget_id": os.getenv("DUFYND_JARVIS_BUDGET_ID"),
        "ready_for_model_execution": active and bool(model) and credentials and supabase,
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
    if not status.get("can_run"):
        raise RuntimeError(
            "DUFYND Jarvis budget window does not permit another run: "
            + json.dumps(status, ensure_ascii=False, default=str)
        )
    configured_model = os.getenv("DUFYND_JARVIS_MODEL")
    budget_model = status.get("model")
    if budget_model and configured_model and budget_model != configured_model:
        raise RuntimeError(
            f"Jarvis budget window requires model {budget_model}, not {configured_model}."
        )
    return budget_id, status


def make_options(bridge: DufyndJarvisBridge) -> ClaudeAgentOptions:
    model, max_turns, max_budget_usd = _require_active_runtime()
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={SERVER_NAME: build_server(bridge)},
        allowed_tools=allowed_tool_names(),
        tools=[],
        cwd=REPO_ROOT,
        env={"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1"},
        model=model,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        permission_mode="dontAsk",
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
    options = make_options(bridge)
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        result = await collect_turn(client)
    if result.is_error:
        detail = "; ".join(result.tool_errors) or result.text or "Jarvis SDK turn failed"
        raise RuntimeError(detail)
    return result.text.strip(), result.cost_usd, resolved_budget_id


async def process_next(bridge: DufyndJarvisBridge) -> int:
    health = await asyncio.to_thread(bridge.load_health)
    if int((health.get("inbox") or {}).get("pending") or 0) == 0:
        print("DUFYND Jarvis inbox: no pending event.")
        return 0

    budget_id, _ = await asyncio.to_thread(_require_budget_window, bridge)
    event = await asyncio.to_thread(bridge.claim_next_inbox_event)
    if event is None:
        print("DUFYND Jarvis inbox: no pending event.")
        return 0

    inbox_id = int(event["inbox_id"])
    attempts = int(event.get("attempts") or 0)
    try:
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
        return 0
    except Exception as error:
        retry = attempts < 3
        await asyncio.to_thread(
            bridge.complete_inbox_event,
            inbox_id=inbox_id,
            status="pending" if retry else "failed",
            error=str(error)[:4000],
        )
        print(
            f"DUFYND Jarvis event {inbox_id} failed; "
            f"{'queued for retry' if retry else 'marked failed'}: {error}",
            file=sys.stderr,
        )
        return 1


async def run_once(prompt: str, bridge: DufyndJarvisBridge) -> int:
    budget_id, _ = await asyncio.to_thread(_require_budget_window, bridge)
    text, cost_usd, _ = await run_prompt(prompt, bridge, budget_id=budget_id)
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
        "--once",
        metavar="PROMPT",
        help="run one manual internal Jarvis task",
    )
    args = parser.parse_args()

    if args.readiness:
        print(json.dumps(runtime_readiness(), ensure_ascii=False))
        return 0

    bridge = DufyndJarvisBridge()
    if args.process_next:
        return asyncio.run(process_next(bridge))
    return asyncio.run(run_once(args.once, bridge))


if __name__ == "__main__":
    raise SystemExit(main())
