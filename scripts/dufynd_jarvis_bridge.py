from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx


def _headers(secret_key: str) -> dict[str, str]:
    headers = {
        "apikey": secret_key,
        "Content-Type": "application/json",
    }
    if secret_key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {secret_key}"
    return headers


@dataclass
class JarvisContextSummary:
    launch_state: str | None
    references: int
    formats: int
    creative_patterns: int
    hook_templates: int
    model_profiles: int
    ideas: int
    lessons: int
    experiments: int
    affiliate_partners: int
    funnel_rows: int
    asset_performance_rows: int
    content_board_items: int
    autonomy_ready: int
    autonomy_approval_required: int
    rubric_metrics: int


class DufyndJarvisBridge:
    """Server-side bridge between Jarvis and the DUFYND Supabase knowledge base.

    The bridge intentionally requires a service-role/secret key. Browser clients
    must never receive this key or direct access to the internal Jarvis tables.
    """

    def __init__(
        self,
        *,
        supabase_url: str | None = None,
        secret_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.supabase_url = (supabase_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.secret_key = (
            secret_key
            or os.getenv("SUPABASE_SECRET_KEY", "")
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        )
        self.transport = transport

        if not self.supabase_url:
            raise ValueError("SUPABASE_URL is required")
        if not self.secret_key:
            raise ValueError("SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY is required")

    def _client(self) -> httpx.Client:
        return httpx.Client(
            timeout=8.0,
            transport=self.transport,
        )

    def _rpc(
        self,
        function_name: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        with self._client() as client:
            response = client.post(
                f"{self.supabase_url}/rest/v1/rpc/{function_name}",
                headers=_headers(self.secret_key),
                json=payload or {},
            )
            response.raise_for_status()
            return response.json()

    def load_context(self) -> dict[str, Any]:
        payload = self._rpc("get_dufynd_jarvis_context")
        if not isinstance(payload, dict):
            raise ValueError("DUFYND Jarvis context must be a JSON object")
        return payload

    def load_creative_context(self) -> dict[str, Any]:
        payload = self._rpc("get_dufynd_jarvis_creative_context")
        if not isinstance(payload, dict):
            raise ValueError("DUFYND Jarvis creative context must be a JSON object")
        return payload

    def load_autonomy_queue(self) -> dict[str, Any]:
        payload = self._rpc("get_dufynd_autonomy_queue")
        if not isinstance(payload, dict):
            raise ValueError("DUFYND Jarvis autonomy queue must be a JSON object")
        return payload

    def load_experiment_rubric(self) -> list[dict[str, Any]]:
        payload = self._rpc("get_dufynd_experiment_rubric")
        if not isinstance(payload, list):
            raise ValueError("DUFYND experiment rubric must be a JSON array")
        return payload

    def load_pending_decisions(self) -> list[dict[str, Any]]:
        payload = self._rpc("get_dufynd_pending_decisions")
        if not isinstance(payload, list):
            raise ValueError("DUFYND pending decisions must be a JSON array")
        return payload

    def load_health(self) -> dict[str, Any]:
        payload = self._rpc("get_dufynd_jarvis_health")
        if not isinstance(payload, dict):
            raise ValueError("DUFYND Jarvis health must be a JSON object")
        return payload

    def load_budget_status(self, budget_id: str) -> dict[str, Any]:
        payload = self._rpc(
            "get_dufynd_jarvis_budget_status",
            {"p_budget_id": budget_id},
        )
        if not isinstance(payload, dict):
            raise ValueError("DUFYND Jarvis budget status must be a JSON object")
        return payload

    def claim_next_inbox_event(self) -> dict[str, Any] | None:
        payload = self._rpc("claim_dufynd_jarvis_event")
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise ValueError("DUFYND Jarvis inbox claim must return an object or null")
        return payload

    def complete_inbox_event(
        self,
        *,
        inbox_id: int,
        status: str = "done",
        error: str | None = None,
    ) -> dict[str, Any]:
        payload = self._rpc(
            "complete_dufynd_jarvis_event",
            {
                "p_inbox_id": inbox_id,
                "p_status": status,
                "p_error": error,
            },
        )
        if not isinstance(payload, dict):
            raise ValueError("DUFYND Jarvis inbox completion must return an object")
        return payload

    def load_rnd_gate(self) -> dict[str, Any]:
        payload = self._rpc("get_dufynd_rnd_gate")
        if not isinstance(payload, dict):
            raise ValueError("DUFYND R&D gate must be a JSON object")
        return payload

    def refresh_rnd_gate(self) -> dict[str, Any]:
        payload = self._rpc("refresh_dufynd_rnd_gate")
        if not isinstance(payload, dict):
            raise ValueError("DUFYND R&D gate refresh must return a JSON object")
        return payload

    def load_launch_gate(self) -> dict[str, Any]:
        payload = self._rpc("get_dufynd_launch_gate")
        if not isinstance(payload, dict):
            raise ValueError("DUFYND launch gate must be a JSON object")
        return payload

    def refresh_launch_gate(self) -> dict[str, Any]:
        payload = self._rpc("refresh_dufynd_launch_gate")
        if not isinstance(payload, dict):
            raise ValueError("DUFYND launch gate refresh must return a JSON object")
        return payload

    def _insert(
        self,
        table: str,
        row: dict[str, Any],
    ) -> None:
        with self._client() as client:
            response = client.post(
                f"{self.supabase_url}/rest/v1/{table}",
                headers={
                    **_headers(self.secret_key),
                    "Prefer": "return=minimal",
                },
                json=row,
            )
            response.raise_for_status()

    def _upsert(
        self,
        table: str,
        row: dict[str, Any],
        *,
        on_conflict: str,
    ) -> None:
        with self._client() as client:
            response = client.post(
                f"{self.supabase_url}/rest/v1/{table}",
                headers={
                    **_headers(self.secret_key),
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                },
                params={"on_conflict": on_conflict},
                json=row,
            )
            response.raise_for_status()

    def record_creative_reference(
        self,
        *,
        label: str,
        category: str,
        summary: str,
        dufynd_application: str,
        quality_notes: str,
        mechanics: list[str] | None = None,
        viral_mechanisms: list[str] | None = None,
        source_uri: str | None = None,
        user_notes: str | None = None,
        status: str = "candidate_reference",
        reference_id: str | None = None,
    ) -> str:
        resolved_id = reference_id or f"reference_{uuid4().hex}"
        self._insert(
            "dufynd_creative_references",
            {
                "id": resolved_id,
                "label": label,
                "category": category,
                "summary": summary,
                "mechanics": mechanics or [],
                "viral_mechanisms": viral_mechanisms or [],
                "dufynd_application": dufynd_application,
                "quality_notes": quality_notes,
                "source_uri": source_uri,
                "user_notes": user_notes,
                "status": status,
            },
        )
        return resolved_id

    def record_creative_pattern(
        self,
        *,
        name: str,
        role: str,
        description: str,
        mechanism: str,
        strengths: list[str] | None = None,
        risks: list[str] | None = None,
        best_for: list[str] | None = None,
        generation_guidance: dict[str, Any] | None = None,
        pattern_id: str | None = None,
    ) -> str:
        resolved_id = pattern_id or f"pattern_{uuid4().hex}"
        self._upsert(
            "dufynd_creative_patterns",
            {
                "pattern_id": resolved_id,
                "name": name,
                "role": role,
                "description": description,
                "mechanism": mechanism,
                "strengths": strengths or [],
                "risks": risks or [],
                "best_for": best_for or [],
                "generation_guidance": generation_guidance or {},
                "status": "active",
            },
            on_conflict="pattern_id",
        )
        return resolved_id

    def link_reference_pattern(
        self,
        *,
        reference_id: str,
        pattern_id: str,
        confidence: float,
        notes: str | None = None,
    ) -> None:
        self._upsert(
            "dufynd_reference_patterns",
            {
                "reference_id": reference_id,
                "pattern_id": pattern_id,
                "confidence": max(0.0, min(confidence, 1.0)),
                "notes": notes,
            },
            on_conflict="reference_id,pattern_id",
        )

    def link_idea_pattern(
        self,
        *,
        idea_id: str,
        pattern_id: str,
        role: str,
        position: int = 1,
        notes: str | None = None,
    ) -> None:
        self._upsert(
            "dufynd_idea_patterns",
            {
                "idea_id": idea_id,
                "pattern_id": pattern_id,
                "role": role,
                "position": max(1, position),
                "notes": notes,
            },
            on_conflict="idea_id,pattern_id,role",
        )

    def record_knowledge_event(
        self,
        *,
        event_type: str,
        source_type: str,
        source_id: str | None,
        payload: dict[str, Any],
    ) -> None:
        self._insert(
            "dufynd_knowledge_events",
            {
                "event_type": event_type,
                "source_type": source_type,
                "source_id": source_id,
                "payload": payload,
            },
        )

    def record_content_idea(
        self,
        *,
        title: str,
        concept: str,
        hook: str,
        format_id: str | None = None,
        fragrance: str | None = None,
        sequence: list[str] | None = None,
        model_candidates: list[str] | None = None,
        priority: int = 50,
        source: str = "jarvis",
        objective: str | None = None,
        target_platforms: list[str] | None = None,
        asset_requirements: list[str] | None = None,
        affiliate_role: str | None = None,
        evaluation_metrics: list[str] | None = None,
        risk_notes: list[str] | None = None,
        hook_template_ids: list[str] | None = None,
        idea_id: str | None = None,
    ) -> str:
        resolved_id = idea_id or f"idea_{uuid4().hex}"
        self._upsert(
            "dufynd_content_ideas",
            {
                "id": resolved_id,
                "title": title,
                "format_id": format_id,
                "fragrance": fragrance,
                "concept": concept,
                "hook": hook,
                "sequence": sequence or [],
                "model_candidates": model_candidates or [],
                "status": "draft",
                "priority": max(0, min(priority, 100)),
                "source": source,
                "objective": objective,
                "target_platforms": target_platforms
                or ["tiktok", "instagram_reels", "youtube_shorts"],
                "asset_requirements": asset_requirements or [],
                "affiliate_role": affiliate_role,
                "evaluation_metrics": evaluation_metrics or [],
                "risk_notes": risk_notes or [],
                "hook_template_ids": hook_template_ids or [],
            },
            on_conflict="id",
        )
        return resolved_id

    def record_content_asset(
        self,
        *,
        content_idea_id: str | None,
        asset_type: str,
        uri: str,
        platform: str | None = None,
        version: int = 1,
        metadata: dict[str, Any] | None = None,
        status: str = "draft",
        content_id: str | None = None,
        asset_id: str | None = None,
    ) -> str:
        resolved_id = asset_id or f"asset_{uuid4().hex}"
        self._insert(
            "dufynd_content_assets",
            {
                "id": resolved_id,
                "content_idea_id": content_idea_id,
                "asset_type": asset_type,
                "platform": platform,
                "version": max(1, version),
                "uri": uri,
                "metadata": metadata or {},
                "status": status,
                "content_id": content_id,
            },
        )
        return resolved_id

    def record_experiment(
        self,
        *,
        model: str,
        prompt_summary: str,
        verdict: str,
        scores: dict[str, float] | None = None,
        content_idea_id: str | None = None,
        result_uri: str | None = None,
        cost_credits: float | None = None,
        cost_eur: float | None = None,
        experiment_id: str | None = None,
    ) -> str:
        resolved_id = experiment_id or f"exp_{uuid4().hex}"
        self._upsert(
            "dufynd_experiments",
            {
                "id": resolved_id,
                "content_idea_id": content_idea_id,
                "model": model,
                "prompt_summary": prompt_summary,
                "result_uri": result_uri,
                "scores": scores or {},
                "verdict": verdict,
                "cost_credits": cost_credits,
                "cost_eur": cost_eur,
            },
            on_conflict="id",
        )
        return resolved_id

    def record_lesson(
        self,
        *,
        domain: str,
        lesson: str,
        evidence: str,
        action_rule: str,
        confidence: float,
        lesson_id: str | None = None,
    ) -> str:
        resolved_id = lesson_id or f"lesson_{uuid4().hex}"
        self._upsert(
            "dufynd_agent_lessons",
            {
                "id": resolved_id,
                "domain": domain,
                "lesson": lesson,
                "evidence": evidence,
                "action_rule": action_rule,
                "confidence": max(0.0, min(confidence, 1.0)),
                "status": "active",
            },
            on_conflict="id",
        )
        return resolved_id

    def record_run(
        self,
        *,
        run_type: str,
        input_summary: str,
        output_summary: str,
        decisions: list[dict[str, Any]] | None = None,
        lessons_written: list[str] | None = None,
        human_approval_required: bool = False,
        human_approval_status: str | None = None,
        agent_name: str = "jarvis",
    ) -> None:
        row = {
            "agent_name": agent_name,
            "run_type": run_type,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "decisions": decisions or [],
            "lessons_written": lessons_written or [],
            "human_approval_required": human_approval_required,
            "human_approval_status": human_approval_status,
        }
        self._insert("dufynd_agent_runs", row)


def summarize_context(
    context: dict[str, Any],
) -> JarvisContextSummary:
    launch_gate = context.get("launch_gate") or {}
    autonomy_queue = context.get("autonomy_queue") or {}
    return JarvisContextSummary(
        launch_state=launch_gate.get("state"),
        references=len(context.get("references") or []),
        formats=len(context.get("formats") or []),
        creative_patterns=len(context.get("creative_patterns") or []),
        hook_templates=len(context.get("hook_templates") or []),
        model_profiles=len(context.get("model_profiles") or []),
        ideas=len(context.get("ideas") or []),
        lessons=len(context.get("lessons") or []),
        experiments=len(context.get("recent_experiments") or []),
        affiliate_partners=len(context.get("affiliate_partners") or []),
        funnel_rows=len(context.get("content_funnel") or []),
        asset_performance_rows=len(context.get("asset_business_performance") or []),
        content_board_items=len(context.get("content_board") or []),
        autonomy_ready=len(autonomy_queue.get("safe_to_execute") or []),
        autonomy_approval_required=len(autonomy_queue.get("approval_required") or []),
        rubric_metrics=len(context.get("experiment_rubric") or []),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read the internal DUFYND Jarvis knowledge and launch state."
    )
    parser.add_argument(
        "command",
        choices=(
            "context",
            "creative-context",
            "autonomy",
            "experiment-rubric",
            "health",
            "rnd-gate",
            "refresh-rnd-gate",
            "launch-gate",
            "refresh-launch-gate",
        ),
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    args = parser.parse_args()

    bridge = DufyndJarvisBridge()

    if args.command == "creative-context":
        payload = bridge.load_creative_context()
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    if args.command == "autonomy":
        payload = bridge.load_autonomy_queue()
        if args.machine_readable:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(
                "DUFYND autonomy queue | "
                f"ready={len(payload.get('safe_to_execute') or [])} | "
                f"in_progress={len(payload.get('in_progress') or [])} | "
                f"waiting_human={len(payload.get('waiting_human_input') or [])} | "
                f"waiting_external={len(payload.get('waiting_external') or [])} | "
                f"approval_required={len(payload.get('approval_required') or [])}"
            )
        return 0

    if args.command == "experiment-rubric":
        payload = bridge.load_experiment_rubric()
        if args.machine_readable:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(
                "DUFYND experiment rubric | "
                f"metrics={len(payload)} | "
                f"hard_fail_metrics="
                f"{sum(1 for metric in payload if metric.get('hard_fail_below') is not None)}"
            )
        return 0

    if args.command == "health":
        payload = bridge.load_health()
        if args.machine_readable:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            inbox = payload.get("inbox") or {}
            print(
                "DUFYND Jarvis health | "
                f"state={payload.get('state')} | "
                f"pending_events={inbox.get('pending', 0)} | "
                f"failed_events={inbox.get('failed', 0)} | "
                f"pending_decisions={payload.get('pending_human_decisions', 0)}"
            )
        return 0

    if args.command in {"rnd-gate", "refresh-rnd-gate"}:
        payload = (
            bridge.refresh_rnd_gate()
            if args.command == "refresh-rnd-gate"
            else bridge.load_rnd_gate()
        )
        if args.machine_readable:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(
                "DUFYND R&D gate | "
                f"state={payload.get('state')} | "
                f"passed={payload.get('passed')}/"
                f"{payload.get('total')} | "
                f"human_pending={payload.get('human_pending')}"
            )
        return 0

    if args.command in {"launch-gate", "refresh-launch-gate"}:
        payload = (
            bridge.refresh_launch_gate()
            if args.command == "refresh-launch-gate"
            else bridge.load_launch_gate()
        )
        if args.machine_readable:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(
                "DUFYND launch gate | "
                f"state={payload.get('state')} | "
                f"passed={payload.get('required_passed')}/"
                f"{payload.get('required_total')}"
            )
        return 0

    payload = bridge.load_context()
    if args.machine_readable:
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    summary = summarize_context(payload)
    print(
        "DUFYND Jarvis context | "
        f"launch={summary.launch_state} | "
        f"refs={summary.references} | "
        f"formats={summary.formats} | "
        f"patterns={summary.creative_patterns} | "
        f"hooks={summary.hook_templates} | "
        f"models={summary.model_profiles} | "
        f"ideas={summary.ideas} | "
        f"lessons={summary.lessons} | "
        f"experiments={summary.experiments} | "
        f"affiliate_partners={summary.affiliate_partners} | "
        f"funnel_rows={summary.funnel_rows} | "
        f"asset_performance_rows={summary.asset_performance_rows} | "
        f"content_board={summary.content_board_items} | "
        f"autonomy_ready={summary.autonomy_ready} | "
        f"approval_required={summary.autonomy_approval_required} | "
        f"rubric_metrics={summary.rubric_metrics}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
