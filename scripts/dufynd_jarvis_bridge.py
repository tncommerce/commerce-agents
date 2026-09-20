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
    ideas: int
    lessons: int
    experiments: int
    affiliate_partners: int
    funnel_rows: int


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
        self.supabase_url = (
            supabase_url or os.getenv("SUPABASE_URL", "")
        ).rstrip("/")
        self.secret_key = (
            secret_key
            or os.getenv("SUPABASE_SECRET_KEY", "")
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        )
        self.transport = transport

        if not self.supabase_url:
            raise ValueError("SUPABASE_URL is required")
        if not self.secret_key:
            raise ValueError(
                "SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY is required"
            )

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

    def load_launch_gate(self) -> dict[str, Any]:
        payload = self._rpc("get_dufynd_launch_gate")
        if not isinstance(payload, dict):
            raise ValueError("DUFYND launch gate must be a JSON object")
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
        idea_id: str | None = None,
    ) -> str:
        resolved_id = idea_id or f"idea_{uuid4().hex}"
        self._insert(
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
        self._insert(
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
        self._insert(
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
    return JarvisContextSummary(
        launch_state=launch_gate.get("state"),
        references=len(context.get("references") or []),
        formats=len(context.get("formats") or []),
        ideas=len(context.get("ideas") or []),
        lessons=len(context.get("lessons") or []),
        experiments=len(context.get("recent_experiments") or []),
        affiliate_partners=len(context.get("affiliate_partners") or []),
        funnel_rows=len(context.get("content_funnel") or []),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read the internal DUFYND Jarvis knowledge and launch state."
    )
    parser.add_argument(
        "command",
        choices=("context", "launch-gate"),
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    args = parser.parse_args()

    bridge = DufyndJarvisBridge()

    if args.command == "launch-gate":
        payload = bridge.load_launch_gate()
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
        f"ideas={summary.ideas} | "
        f"lessons={summary.lessons} | "
        f"experiments={summary.experiments} | "
        f"affiliate_partners={summary.affiliate_partners} | "
        f"funnel_rows={summary.funnel_rows}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
