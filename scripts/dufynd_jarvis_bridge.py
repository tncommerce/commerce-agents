from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx
from scripts.dufynd_jarvis_control_plane import HUMAN_REASONS


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
        self.worker_tokens: dict[str, str] = {}

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

    def reserve_model_call(self, **payload: Any) -> dict[str, Any]:
        return self._rpc(
            "reserve_dufynd_model_call", {f"p_{key}": value for key, value in payload.items()}
        )

    def dispatch_model_call(self, reservation_id: str, lease_token: str) -> bool:
        return (
            self._rpc(
                "dispatch_dufynd_model_call",
                {
                    "p_reservation_id": reservation_id,
                    "p_lease_token": lease_token,
                },
            )
            is True
        )

    def settle_model_call(
        self, reservation_id: str, lease_token: str, actual_usd: str, evidence: dict[str, Any]
    ) -> bool:
        return (
            self._rpc(
                "settle_dufynd_model_call",
                {
                    "p_reservation_id": reservation_id,
                    "p_lease_token": lease_token,
                    "p_actual_usd": actual_usd,
                    "p_evidence": evidence,
                },
            )
            is True
        )

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

    def load_creative_pattern_index(self, *, limit: int = 100) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(int(limit), 200))
        with self._client() as client:
            response = client.get(
                f"{self.supabase_url}/rest/v1/dufynd_creative_patterns",
                headers=_headers(self.secret_key),
                params={
                    "select": "pattern_id,name,role,mechanism,best_for",
                    "order": "pattern_id.asc",
                    "limit": str(bounded_limit),
                },
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list):
            raise ValueError("DUFYND creative-pattern index must return a JSON array")
        return [row for row in payload if isinstance(row, dict)]

    def load_autonomy_queue(self) -> dict[str, Any]:
        payload = self._rpc("get_dufynd_autonomy_queue")
        if not isinstance(payload, dict):
            raise ValueError("DUFYND Jarvis autonomy queue must be a JSON object")
        return payload

    def load_master_status_entry(self, key: str) -> dict[str, Any] | None:
        with self._client() as client:
            response = client.get(
                f"{self.supabase_url}/rest/v1/dufynd_master_status",
                headers=_headers(self.secret_key),
                params={
                    "select": "*",
                    "key": f"eq.{key}",
                    "limit": "1",
                },
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list):
            raise ValueError("DUFYND master-status lookup must return a JSON array")
        if not payload:
            return None
        row = payload[0]
        if not isinstance(row, dict):
            raise ValueError("DUFYND master-status row must be a JSON object")
        return row

    def load_autonomy_task(self, task_id: str) -> dict[str, Any] | None:
        with self._client() as client:
            response = client.get(
                f"{self.supabase_url}/rest/v1/dufynd_autonomy_tasks",
                headers=_headers(self.secret_key),
                params={
                    "select": "*",
                    "task_id": f"eq.{task_id}",
                    "limit": "1",
                },
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list):
            raise ValueError("DUFYND autonomy task lookup must return a JSON array")
        if not payload:
            return None
        row = payload[0]
        if not isinstance(row, dict):
            raise ValueError("DUFYND autonomy task row must be a JSON object")
        return row

    def load_agent_runs_since(self, since_iso: str) -> list[dict[str, Any]]:
        with self._client() as client:
            response = client.get(
                f"{self.supabase_url}/rest/v1/dufynd_agent_runs",
                headers=_headers(self.secret_key),
                params={
                    "select": "*",
                    "created_at": f"gte.{since_iso}",
                    "order": "created_at.asc",
                },
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list):
            raise ValueError("DUFYND agent-run lookup must return a JSON array")
        return [row for row in payload if isinstance(row, dict)]

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

    def project_broker_health(self, health: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(health, dict):
            raise ValueError("Broker health must be a JSON object")
        payload = self._rpc("project_dufynd_broker_health", {"p_health": health})
        if not isinstance(payload, dict):
            raise ValueError("Broker health projection must return a JSON object")
        return payload

    def capture_broker_observation(
        self,
        *,
        credential_id: str,
        observer_id: str,
        evidence: Any,
    ) -> dict[str, Any]:
        if not credential_id.strip() or not observer_id.strip():
            raise ValueError("Broker credential_id and observer_id are required")
        if not isinstance(evidence, (dict, list)):
            raise ValueError("Broker evidence must be a JSON object or array")
        payload = self._rpc(
            "capture_dufynd_broker_observation",
            {
                "p_credential_id": credential_id,
                "p_observer_id": observer_id,
                "p_evidence": evidence,
            },
        )
        if not isinstance(payload, dict):
            raise ValueError("Broker observation capture must return a JSON object")
        return payload

    def begin_broker_acceptance(self, source: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(source, dict):
            raise ValueError("Broker acceptance source must be a JSON object")
        payload = self._rpc("begin_dufynd_broker_acceptance", {"p_source": source})
        if not isinstance(payload, dict):
            raise ValueError("Broker acceptance begin must return a JSON object")
        return payload

    def capture_broker_acceptance_observation(
        self,
        *,
        run_id: int,
        credential_id: str,
        observer_id: str,
        evidence: Any,
    ) -> dict[str, Any]:
        if run_id <= 0:
            raise ValueError("Broker acceptance run_id must be positive")
        payload = self._rpc(
            "capture_dufynd_broker_acceptance_observation",
            {
                "p_run_id": run_id,
                "p_credential_id": credential_id,
                "p_observer_id": observer_id,
                "p_evidence": evidence,
            },
        )
        if not isinstance(payload, dict):
            raise ValueError("Broker acceptance capture must return a JSON object")
        return payload

    def finalize_broker_acceptance(
        self,
        *,
        source: dict[str, Any],
        ack_summary: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self._rpc(
            "finalize_dufynd_broker_acceptance",
            {"p_source": source, "p_ack_summary": ack_summary},
        )
        if not isinstance(payload, dict):
            raise ValueError("Broker acceptance finalization must return a JSON object")
        return payload

    def load_budget_status(self, budget_id: str) -> dict[str, Any]:
        payload = self._rpc(
            "get_dufynd_jarvis_budget_status",
            {"p_budget_id": budget_id},
        )
        if not isinstance(payload, dict):
            raise ValueError("DUFYND Jarvis budget status must be a JSON object")
        return payload

    def load_budget_window(self, budget_id: str) -> dict[str, Any] | None:
        with self._client() as client:
            response = client.get(
                f"{self.supabase_url}/rest/v1/dufynd_jarvis_budget_windows",
                headers=_headers(self.secret_key),
                params={
                    "select": "*",
                    "budget_id": f"eq.{budget_id}",
                    "limit": "1",
                },
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list):
            raise ValueError("DUFYND Jarvis budget-window lookup must return a JSON array")
        if not payload:
            return None
        row = payload[0]
        if not isinstance(row, dict):
            raise ValueError("DUFYND Jarvis budget-window row must be a JSON object")
        return row

    def load_human_decision(self, decision_id: str) -> dict[str, Any] | None:
        with self._client() as client:
            response = client.get(
                f"{self.supabase_url}/rest/v1/dufynd_human_decisions",
                headers=_headers(self.secret_key),
                params={
                    "select": "*",
                    "decision_id": f"eq.{decision_id}",
                    "limit": "1",
                },
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list):
            raise ValueError("DUFYND human-decision lookup must return a JSON array")
        if not payload:
            return None
        row = payload[0]
        if not isinstance(row, dict):
            raise ValueError("DUFYND human-decision row must be a JSON object")
        return row

    def complete_pending_human_decision_reconciliation(
        self,
        *,
        decision_id: str,
        decision: dict[str, Any],
        resolved_at: str,
    ) -> dict[str, Any] | None:
        if not decision_id.strip():
            raise ValueError("decision_id is required")
        if not isinstance(decision, dict) or not decision:
            raise ValueError("reconciliation decision payload must be a non-empty object")
        if not resolved_at.strip():
            raise ValueError("resolved_at is required")

        with self._client() as client:
            response = client.patch(
                f"{self.supabase_url}/rest/v1/dufynd_human_decisions",
                headers={
                    **_headers(self.secret_key),
                    "Prefer": "return=representation",
                },
                params={
                    "decision_id": f"eq.{decision_id}",
                    "status": "eq.pending",
                },
                json={
                    "status": "completed",
                    "decision": decision,
                    "decided_at": resolved_at,
                    "completed_at": resolved_at,
                },
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list):
            raise ValueError("DUFYND decision reconciliation must return a JSON array")
        if not payload:
            return None
        row = payload[0]
        if not isinstance(row, dict):
            raise ValueError("DUFYND reconciled decision row must be a JSON object")
        return row

    def complete_pending_autonomy_task_reconciliation(
        self,
        *,
        task_id: str,
        status: str,
        evidence: str,
    ) -> dict[str, Any] | None:
        if not task_id.strip():
            raise ValueError("task_id is required")
        if status not in {"done", "cancelled"}:
            raise ValueError("Reconciled autonomy task status must be done or cancelled.")

        with self._client() as client:
            response = client.patch(
                f"{self.supabase_url}/rest/v1/dufynd_autonomy_tasks",
                headers={
                    **_headers(self.secret_key),
                    "Prefer": "return=representation",
                },
                params={
                    "task_id": f"eq.{task_id}",
                    "status": "eq.approval_required",
                    "approval_action_type": "eq.merge_production_code",
                },
                json={
                    "status": status,
                    "evidence": evidence[:12000],
                },
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list):
            raise ValueError("DUFYND task reconciliation must return a JSON array")
        if not payload:
            return None
        row = payload[0]
        if not isinstance(row, dict):
            raise ValueError("DUFYND reconciled autonomy task row must be a JSON object")
        return row

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

    def update_autonomy_task_progress(
        self,
        *,
        task_id: str,
        status: str,
        evidence: str,
    ) -> None:
        allowed_statuses = {
            "in_progress",
            "waiting_human_input",
            "waiting_external",
            "blocked",
        }
        if status not in allowed_statuses:
            raise ValueError("Safe worker may only record non-terminal autonomy task progress.")
        if task_id in self.worker_tokens:
            self.update_worker(task_id, "working", evidence=evidence)
            return
        with self._client() as client:
            response = client.patch(
                f"{self.supabase_url}/rest/v1/dufynd_autonomy_tasks",
                headers={
                    **_headers(self.secret_key),
                    "Prefer": "return=minimal",
                },
                params={"task_id": f"eq.{task_id}"},
                json={
                    "status": status,
                    "evidence": evidence[:12000],
                },
            )
            response.raise_for_status()

    def set_autonomy_task_status(
        self,
        *,
        task_id: str,
        status: str,
        evidence: str,
    ) -> None:
        allowed_statuses = {
            "ready",
            "in_progress",
            "done",
            "waiting_human_input",
            "waiting_external",
            "blocked",
            "approval_required",
        }
        if status not in allowed_statuses:
            raise ValueError(f"Unsupported DUFYND autonomy task status: {status}")
        if task_id in self.worker_tokens:
            state = {"ready": "queued", "in_progress": "working"}.get(status, status)
            reason = {
                "waiting_external": "external_dependency",
            }.get(status)
            if status == "waiting_human_input":
                reason = next(
                    (
                        r
                        for r in HUMAN_REASONS
                        if f"DUFYND_BLOCK_REASON: {r}" in evidence.splitlines()
                    ),
                    None,
                )
            self.update_worker(task_id, state, evidence=evidence, reason=reason)
            return
        with self._client() as client:
            response = client.patch(
                f"{self.supabase_url}/rest/v1/dufynd_autonomy_tasks",
                headers={
                    **_headers(self.secret_key),
                    "Prefer": "return=minimal",
                },
                params={"task_id": f"eq.{task_id}"},
                json={
                    "status": status,
                    "evidence": evidence[:12000],
                },
            )
            response.raise_for_status()

    def reconcile_control_plane(self) -> dict[str, Any]:
        result = self._rpc("reconcile_dufynd_supervisor_v2")
        if not isinstance(result, dict):
            raise ValueError("Supervisor reconciliation must return an object")
        return result

    def claim_worker(self, task_id: str, owner: str) -> dict[str, Any] | None:
        token = str(uuid4())
        result = self._rpc(
            "claim_dufynd_worker_v2", {"p_task_id": task_id, "p_owner": owner, "p_token": token}
        )
        if result is not None:
            if not isinstance(result, dict):
                raise ValueError("Worker claim must return an object or null")
            self.worker_tokens[task_id] = token
        return result

    def update_worker(
        self, task_id: str, state: str, *, evidence: str | None = None, reason: str | None = None
    ) -> None:
        accepted = self._rpc(
            "update_dufynd_worker_v2",
            {
                "p_task_id": task_id,
                "p_token": self.worker_tokens.get(task_id),
                "p_state": state,
                "p_evidence": evidence[:12000] if evidence else None,
                "p_reason": reason,
            },
        )
        if accepted is not True:
            raise RuntimeError("Worker lease lost; refusing stale write")

    def upsert_master_status(
        self,
        *,
        key: str,
        category: str,
        value: dict[str, Any],
        priority: int = 100,
        last_verified_at: str | None = None,
    ) -> None:
        self._upsert(
            "dufynd_master_status",
            {
                "key": key,
                "category": category,
                "value": value,
                "priority": max(0, min(priority, 100)),
                "last_verified_at": last_verified_at,
            },
            on_conflict="key",
        )

    def upsert_autonomy_task(
        self,
        *,
        task_id: str,
        domain: str,
        title: str,
        instruction: str,
        status: str,
        priority: int,
        requires_human_approval: bool,
        approval_action_type: str | None = None,
        dependencies: list[str] | None = None,
        evidence: str | None = None,
        owner: str = "jarvis",
    ) -> None:
        self._upsert(
            "dufynd_autonomy_tasks",
            {
                "task_id": task_id,
                "domain": domain,
                "title": title,
                "instruction": instruction,
                "status": status,
                "priority": max(0, min(priority, 100)),
                "requires_human_approval": requires_human_approval,
                "approval_action_type": approval_action_type,
                "dependencies": dependencies or [],
                "evidence": evidence,
                "owner": owner,
            },
            on_conflict="task_id",
        )

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
        autonomy_approval_required=len(autonomy_queue.get("appr…18706 tokens truncated…ss_audit','steps',1,'interval_seconds',2,"
        "'offer_id',offer_id,'product_id',product_id,'canonical_identity',canonical_identity,'offer_contract',offer_contract,"
        "'last_verified_at',last_verified_at,'expiry',last_verified_at+interval '72 hours',"
        "'verification_contract','perfumetrader_exact_html_v1','allowed_mutations','[\"verification_evidence\"]'::jsonb)"
        " from dufynd_purchase_verification_targets where offer_id=%s",
        (PURCHASE_OFFER,),
    )


def purchase_decision(html=PURCHASE_HTML, shipping=PURCHASE_SHIPPING, payload=None):
    import json

    return query(
        "select evaluate_dufynd_purchase_page(%s::jsonb,%s,%s,200,200)",
        (json.dumps(payload or purchase_payload()), html, shipping),
    )["decision"]


def test_purchase_safe_identity_refresh(purchase_net):
    assert purchase_decision() == "safe_evidence_refresh"


@pytest.mark.parametrize(
    ("old", "new", "decision"),
    [
        ("71.9000", "70.9000", "price_review_required"),
        ("InStock", "OutOfStock", "stock_unverified_or_changed"),
        ("100 ml", "50 ml", "variant_identity_mismatch"),
        ("Eau de Toilette", "Eau de Parfum", "variant_identity_mismatch"),
        ("16978322", "16978323", "merchant_identity_mismatch"),
        ("3349666007921", "3349666007891", "gtin_mismatch"),
        ("100 ml", "100 ml Refill", "variant_identity_mismatch"),
    ],
)
def test_purchase_exact_variant_price_and_stock_fail_closed(purchase_net, old, new, decision):
    assert purchase_decision(PURCHASE_HTML.replace(old, new)) == decision


def test_purchase_invalid_route_never_refreshes(purchase_net):
    payload = purchase_payload()
    payload["offer_contract"]["affiliate_url"] += "&awinmid=99999"
    assert purchase_decision(payload=payload) == "route_contract_mismatch"


def test_purchase_shipping_change_requires_review(purchase_net):
    assert purchase_decision(shipping="Versandkosten 5,99 €") == "shipping_review_required"


def test_purchase_fresh_offer_no_wake(purchase_net):
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(
            "update dufynd_purchase_verification_targets set enabled=true,certification_due=false,last_result=null,last_verified_at=now()"
        )
    assert query("select wake_dufynd_purchase_freshness()") == {"wake_events": 0}


def test_purchase_pre_expiry_before_today_regression(purchase_net):
    # The real 09-29 12:04:36 verification would wake 10-01 12:04:36,
    # a full day before the 10-02 12:04:36 production exclusion.
    assert query(
        "select '2026-09-29T12:04:36Z'::timestamptz + make_interval(hours=>max_age_hours-safety_window_hours)"
        " < '2026-10-02T12:04:36Z'::timestamptz from dufynd_purchase_verification_targets"
    )
    from datetime import UTC, datetime

    assert query(
        "select '2026-09-29T12:04:36Z'::timestamptz + make_interval(hours=>max_age_hours-safety_window_hours)"
        " from dufynd_purchase_verification_targets"
    ) == datetime(2026, 10, 1, 12, 4, 36, tzinfo=UTC)


def test_purchase_live_chain_deduplicates_and_fences(purchase_net):
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(
            "update dufynd_purchase_verification_targets set enabled=false,certification_due=true,last_result=null"
        )
    assert query("select wake_dufynd_purchase_freshness()") == {"wake_events": 1}
    assert query("select wake_dufynd_purchase_freshness()") == {"wake_events": 0}
    query("select process_dufynd_external_events()")
    eid = query(
        "select execution_id from dufynd_execution_runs where task_id='purchase_freshness_acceptance_20261002'"
    )
    e = query("select take_dufynd_execution('999999','purchase-test',%s)", (eid,))
    assert e["task_packet"]["payload"]["allowed_mutations"] == ["verification_evidence"]
    assert query("select take_dufynd_execution('999998','duplicate-worker',%s)", (eid,)) is None
    assert (
        query("select checkpoint_dufynd_execution(%s,%s,'wrong-worker',1)", (eid, e["lease_token"]))
        is None
    )
    query("select checkpoint_dufynd_execution(%s,%s,'purchase-test',1)", (eid, e["lease_token"]))
    verified = query(
        "select checkpoint_dufynd_execution(%s,%s,'purchase-test',1)", (eid, e["lease_token"])
    )
    assert verified["last_checkpoint"]["audit"]["decision"] == "safe_evidence_refresh"
    assert query("select finish_dufynd_execution(%s,%s,'purchase-test')", (eid, e["lease_token"]))
    assert query("select certify_dufynd_purchase_freshness(%s)", (eid,))
    assert (
        query(
            "select count(*) from dufynd_purchase_verification_evidence where execution_id=%s",
            (eid,),
        )
        == 1
    )
    assert (
        query(
            "select status from dufynd_autonomy_tasks where task_id='purchase_freshness_acceptance_20261002'"
        )
        == "done"
    )


def test_purchase_approaching_expiry_wake_and_chatless_recovery(purchase_net):
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(
            "update dufynd_purchase_verification_targets set enabled=true,certification_due=false,last_result=null,last_verified_at=now()-interval '49 hours'"
        )
    assert query("select wake_dufynd_purchase_freshness()") == {"wake_events": 1}
    query("select process_dufynd_external_events()")
    eid = query(
        "select execution_id from dufynd_execution_runs where handler_id='purchase_destination_freshness_audit' and status='dispatch_pending'"
    )
    e = query("select take_dufynd_execution('888888','crash-worker',%s)", (eid,))
    assert query(
        "select fail_dufynd_execution(%s,%s,'crash-worker','simulated_crash')",
        (eid, e["lease_token"]),
    )
    query("select reconcile_dufynd_executions()")
    assert (
        query("select checkpoint_dufynd_execution(%s,%s,'crash-worker',1)", (eid, e["lease_token"]))
        is None
    )
    for _ in range(3):
        query("select reconcile_dufynd_executions()")
    final = query(
        "select row_to_json(e)::jsonb from dufynd_execution_runs e where execution_id=%s", (eid,)
    )
    assert final["status"] == "completed"
    assert final["worker_type"] == "deterministic_supervisor"
    assert final["packet_hash"] == e["packet_hash"]
    assert final["recovery_count"] >= 1
    assert (
        query(
            "select count(*) from dufynd_purchase_verification_evidence where execution_id=%s",
            (eid,),
        )
        == 1
    )


def test_purchase_unknown_capability_cannot_dispatch(purchase_net):
    import json

    import psycopg

    tid = f"purchase-unknown-{uuid4()}"
    resources = f'["db:purchase-evidence:{PURCHASE_OFFER}"]'
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(
            "insert into dufynd_autonomy_tasks(task_id,domain,title,instruction,status,budget_class,durability_policy,resource_scope,required_capabilities) values(%s,'supervisor','test','test','ready','free','durable',%s::jsonb,'[\"unknown.capability\"]')",
            (tid, resources),
        )
    denied = query(
        "select prepare_dufynd_execution(%s,%s,'supervisor',%s::jsonb,%s::jsonb,'durable')",
        (tid, tid, resources, json.dumps(purchase_payload())),
    )
    assert not denied["allowed"]
    assert query("select count(*) from dufynd_execution_runs where task_id=%s", (tid,)) == 0


def test_purchase_concurrent_same_offer_has_one_owner(purchase_net):
    import json

    payload = json.dumps(purchase_payload())
    resource = f'["db:purchase-evidence:{PURCHASE_OFFER}"]'
    tids = [f"purchase-concurrent-{uuid4()}" for _ in range(2)]
    barrier = Barrier(2)

    def claim(tid):
        barrier.wait()
        return query(
            "select prepare_dufynd_execution(%s,%s,'supervisor',%s::jsonb,%s::jsonb,'durable')",
            (tid, tid, resource, payload),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, tids))
    assert sum(x["allowed"] for x in outcomes) == 1
    winner = next(x["execution"] for x in outcomes if x["allowed"])
    for _ in range(3):
        query("select reconcile_dufynd_executions()")
    assert (
        query(
            "select status from dufynd_execution_runs where execution_id=%s",
            (winner["execution_id"],),
        )
        == "completed"
    )


def test_purchase_non_200_never_creates_safe_evidence(purchase_net):
    import json

    result = query(
        "select evaluate_dufynd_purchase_page(%s::jsonb,%s,%s,403,200)",
        (json.dumps(purchase_payload()), PURCHASE_HTML, PURCHASE_SHIPPING),
    )
    assert result["decision"] == "transport_unverified"


def test_purchase_ambiguous_primary_fields_fail_closed(purchase_net):
    assert purchase_decision(PURCHASE_HTML + '\n"productSku":"other"') == "ambiguous_primary_fields"


def test_purchase_visible_variant_disagrees_with_metadata(purchase_net):
    html = PURCHASE_HTML.replace("100 ml</h1>", "50 ml</h1>")
    assert purchase_decision(html) == "variant_identity_mismatch"


def test_purchase_acceptance_receipt_projects_existing_evidence(purchase_net):
    import json

    eid = query(
        "select execution_id from dufynd_execution_runs where task_id='purchase_freshness_acceptance_20261002'"
    )
    query(
        "insert into dufynd_master_status(key,value) values('jarvis.purchase_freshness.acceptance',%s::jsonb) on conflict(key) do update set value=excluded.value returning key",
        (
            json.dumps(
                {
                    "status": "armed",
                    "task_id": "purchase_freshness_acceptance_20261002",
                    "execution_id": str(eid),
                }
            ),
        ),
    )
    query("select project_dufynd_acceptance_receipts()")
    receipt = query(
        "select value from dufynd_master_status where key='jarvis.purchase_freshness.acceptance'"
    )
    assert receipt["status"] == "live_execution_verified"
    assert receipt["execution_receipt"]["execution_verified"]
    assert receipt["execution_receipt"]["lease_released"]
    assert receipt["execution_receipt"]["report_hash"]
    assert query("select project_dufynd_acceptance_receipts()")["projected"] == 0


def ci_pr_target(*, acceptance=False):
    pr = str(100000 + uuid4().int % 800000000)
    run = str(10000000000 + uuid4().int % 80000000000)
    scheduled = query(
        "select schedule_dufynd_ci_pr_verification(%s,%s,%s,%s,%s)",
        (pr, run, "a" * 40, "b" * 40, acceptance),
    )
    assert scheduled["scheduled"]
    payload = task_state(scheduled["task_id"])["durable_payload"]
    pr_raw = {
        "number": int(pr),
        "merged": True,
        "state": "closed",
        "base": {"ref": "scentai-mvp", "sha": "a" * 40},
        "head": {"sha": "b" * 40},
        "merge_commit_sha": "a" * 40,
        "updated_at": "2026-10-02T13:00:00Z",
    }
    capture("github_pr:" + pr, pr_raw)
    capture("github_ci:" + run, ci_raw(run))
    return scheduled["task_id"], payload, pr_raw


@pytest.fixture(scope="module")
def ci_pr_admitted():
    assert not query(
        "select schedule_dufynd_ci_pr_verification('623','37014817569',%s,%s)", ("a" * 40, "b" * 40)
    )["scheduled"]
    task, payload, raw = ci_pr_target(acceptance=True)
    assert query("select process_dufynd_external_events()")
    query("select reconcile_dufynd_executions()")
    e = query("select to_jsonb(e) from dufynd_execution_runs e where task_id=%s", (task,))
    assert e["status"] == "completed"
    assert e["last_checkpoint"]["audit"]["decision"] == "verified"
    assert query("select certify_dufynd_ci_pr_verifier(%s)", (e["execution_id"],))
    return e


def test_ci_pr_free_acceptance_registry_receipt_and_packet(ci_pr_admitted):
    import json

    e = ci_pr_admitted
    assert e["worker_type"] == "deterministic_supervisor"
    assert task_state(e["task_id"])["released_at"]
    assert e["task_packet"]["required_capabilities"] == [
        "github.ci.observe",
        "github.read",
        "supabase.execution_state",
        "supabase.task_state",
    ]
    assert e["last_checkpoint"]["audit"]["deployment_verified"] is False
    query(
        "insert into dufynd_master_status(key,value) values('jarvis.ci_pr_verifier.acceptance',%s::jsonb) returning key",
        (
            json.dumps(
                {
                    "task_id": e["task_id"],
                    "execution_id": e["execution_id"],
                    "status": "live_accepted",
                }
            ),
        ),
    )
    query("select project_dufynd_acceptance_receipts()")
    receipt = query(
        "select value->'execution_receipt' from dufynd_master_status where key='jarvis.ci_pr_verifier.acceptance'"
    )
    assert receipt["execution_verified"] and receipt["dispatch_count"] == 1
    assert receipt["report_hash"] == e["last_checkpoint"]["audit_hash"]
    assert not receipt["ci_acceptance_inferred"]


@pytest.mark.parametrize(
    "change,decision",
    [
        ("pr_head", "pr_sha_mismatch"),
        ("pr_merge", "pr_sha_mismatch"),
        ("ci_sha", "ci_sha_mismatch"),
        ("ci_failed", "ci_not_successful"),
        ("ci_queued", "ci_not_successful"),
        ("pr_open", "pr_not_merged_to_integration"),
        ("stale", "source_unverified_or_stale"),
        ("unhealthy", "source_unverified_or_stale"),
    ],
)
def test_ci_pr_exact_truth_fail_closed(ci_pr_admitted, change, decision):
    import json

    task, payload, raw = ci_pr_target()
    run = payload["ci_run_id"]
    if change in ("pr_head", "pr_merge", "pr_open"):
        if change == "pr_head":
            raw["head"]["sha"] = "c" * 40
        if change == "pr_merge":
            raw["merge_commit_sha"] = "c" * 40
        if change == "pr_open":
            raw.update(merged=False, state="open")
        capture("github_pr:" + payload["pr_number"], raw)
    if change == "ci_sha":
        capture("github_ci:" + run, ci_raw(run, sha="c" * 40))
    if change == "ci_failed":
        capture("github_ci:" + run, ci_raw(run, conclusion="failure"))
    if change == "ci_queued":
        capture("github_ci:" + run, ci_raw(run, state="queued", conclusion=None))
    if change == "stale":
        query(
            "update dufynd_external_observers set last_success_at=now()-interval '21 minutes' where observer_id=%s returning true",
            ("github_ci:" + run,),
        )
    if change == "unhealthy":
        query("select dufynd_observer_failure(%s,'transport_failure',500)", ("github_ci:" + run,))
    report = query("select read_dufynd_ci_pr_audit(%s::jsonb)", (json.dumps(payload),))
    assert report["decision"] == decision
    assert not report["approvals_inferred"] and not report["business_mutations"]
    # Retire this isolated fixture target before later global event reevaluation.
    query("update dufynd_autonomy_tasks set status='done' where task_id=%s returning true", (task,))


@pytest.mark.parametrize("pr", ["1", "598", "0", "main", "622;select 1"])
def test_ci_pr_protected_or_invalid_targets_not_scheduled(ci_pr_admitted, pr):
    assert not query(
        "select schedule_dufynd_ci_pr_verification(%s,'37014817569',%s,%s)",
        (pr, "a" * 40, "b" * 40),
    )["scheduled"]


def test_ci_pr_main_and_wrong_workflow_rejected(ci_pr_admitted):
    import psycopg

    task, payload, raw = ci_pr_target()
    raw["base"]["ref"] = "main"
    with pytest.raises(psycopg.errors.RaiseException, match="PR identity mismatch"):
        capture("github_pr:" + payload["pr_number"], raw)
    bad = ci_raw(payload["ci_run_id"])
    bad["path"] = ".github/workflows/not-ci.yml"
    with pytest.raises(psycopg.errors.RaiseException, match="CI workflow mismatch"):
        capture("github_ci:" + payload["ci_run_id"], bad)
    query("update dufynd_autonomy_tasks set status='done' where task_id=%s returning true", (task,))


def test_ci_pr_duplicate_event_schedule_and_chatless_completion(ci_pr_admitted):
    task, payload, raw = ci_pr_target()
    again = query(
        "select schedule_dufynd_ci_pr_verification(%s,%s,%s,%s)",
        tuple(
            payload[k]
            for k in ("pr_number", "ci_run_id", "expected_merge_sha", "expected_pr_head_sha")
        ),
    )
    assert again["reused"] and again["task_id"] == task
    assert capture("github_pr:" + payload["pr_number"], raw)["inserted"] == 0
    query("select process_dufynd_external_events()")
    query("select process_dufynd_external_events()")
    query("select reconcile_dufynd_executions()")
    e = query("select to_jsonb(e) from dufynd_execution_runs e where task_id=%s", (task,))
    assert e["status"] == "completed" and task_state(task)["status"] == "done"
    assert query("select count(*) from dufynd_execution_runs where task_id=%s", (task,)) == 1
    assert (
        query(
            "select count(*) from dufynd_ci_pr_verification_evidence where execution_id=%s",
            (e["execution_id"],),
        )
        == 1
    )


def test_ci_pr_changed_ci_after_dispatch_blocks_completion(ci_pr_admitted):
    task, payload, raw = ci_pr_target()
    query("select process_dufynd_external_events()")
    capture("github_ci:" + payload["ci_run_id"], ci_raw(payload["ci_run_id"], conclusion="failure"))
    query("select reconcile_dufynd_executions()")
    assert task_state(task)["status"] == "blocked"
    assert task_state(task)["blocked_reason"] == "ci_not_successful"


def test_ci_pr_unknown_capability_prevents_dispatch(ci_pr_admitted):
    task, payload, raw = ci_pr_target()
    query(
        "update dufynd_autonomy_tasks set required_capabilities='[\"github.unknown\"]' where task_id=%s returning true",
        (task,),
    )
    query("select process_dufynd_external_events()")
    assert query("select count(*) from dufynd_execution_runs where task_id=%s", (task,)) == 0


def test_ci_pr_crash_rotates_fence_and_resumes_same_packet(ci_pr_admitted):
    task, payload, raw = ci_pr_target()
    query("select process_dufynd_external_events()")
    e = query("select to_jsonb(e) from dufynd_execution_runs e where task_id=%s", (task,))
    e = take_execution(e)
    force_execution_expired(e)
    query("select reconcile_dufynd_executions()")
    assert execution_checkpoint(e, 1) is None
    query("select reconcile_dufynd_executions()")
    finished = execution_state(e)
    assert finished["status"] == "completed"
    assert finished["packet_hash"] == e["packet_hash"]
    assert finished["recovery_count"] == 1
    assert task_state(task)["released_at"]


@pytest.mark.parametrize(
    ("task_changes", "execution", "reason"),
    [
        (
            {"worker_state": "done", "status": "done", "released_at": "2026-10-02T12:00:00Z"},
            {"status": "completed", "lease_token": "a"},
            None,
        ),
        ({"lease_expires_at": "2026-10-02T11:00:00Z"}, None, "expired_active_lease"),
        ({"released_at": "2026-10-02T11:00:00Z"}, None, "active_released_lease"),
        ({"heartbeat_at": "2026-10-02T11:00:00Z"}, None, "stale_heartbeat"),
        ({"last_progress_at": "2026-10-02T11:00:00Z"}, None, "progress_stalled"),
        ({}, {"status": "completed", "lease_token": "a"}, "completed_execution_unreleased_lease"),
        (
            {"status": "done"},
            {"status": "running", "lease_token": "a"},
            "done_task_running_execution",
        ),
        ({}, {"status": "running", "lease_token": "old"}, "stale_fencing_token"),
        (
            {"worker_owner": None},
            {"status": "retryable", "lease_token": "a"},
            "retryable_without_owner",
        ),
        ({"status": "invented"}, None, "unknown_state"),
    ],
)
def test_recovery_audit_readonly_classification(task_changes, execution, reason):
    import json

    task = {
        "status": "in_progress",
        "worker_state": "working",
        "lease_token": "a",
        "worker_owner": "durable_recovery",
        "released_at": None,
        "lease_expires_at": "2026-10-02T12:03:00Z",
        "heartbeat_at": "2026-10-02T12:00:00Z",
        "last_progress_at": "2026-10-02T12:00:00Z",
    } | task_changes
    args = (json.dumps(task), json.dumps(execution) if execution else None)
    sql = "select dufynd_recovery_findings(%s::jsonb,%s::jsonb,'2026-10-02T12:00:00Z')"
    first = query(sql, args)
    assert first == query(sql, args)  # duplicate/retry requires no persisted audit owner
    assert (reason in first) if reason else first == []


def test_extended_audit_preserves_existing_packet_and_no_chat_contract():
    before = query("select count(*) from dufynd_execution_runs")
    audit = query("select read_dufynd_supervisor_audit()")
    assert audit["extension_revision"] == 2
    assert not audit["recovery_consistency"]["repair_performed"]
    assert not audit["dependency_readiness"]["state_mutated"]
    assert audit["unknown_state_fail_closed"] and not audit["chat_history_required"]
    assert query("select count(*) from dufynd_execution_runs") == before


def broker_health_payload(*, checked_at=None):
    checked = checked_at or datetime.now(UTC)
    return {
        "render": {
            "credential_id": "render_deploy_broker",
            "provider": "render",
            "account_alias": "tncommerce_render",
            "allowed_operations": ["deployment.read"],
            "allowed_resources": ["srv-dakpfrnf3r2c73dr3f20"],
            "oauth_scopes": [],
            "secret_reference": "dufynd_observer_render_read_token",
            "status": "healthy",
            "expires_at": None,
            "refreshed_at": None,
            "revoked_at": None,
            "last_health_check": checked.isoformat(),
            "health_reason": "healthy",
            "rotation_due_at": None,
        },
        "gmail": {
            "credential_id": "gmail_known_threads",
            "provider": "gmail",
            "account_alias": "dufynd_owner_mailbox",
            "allowed_operations": ["thread.metadata", "history.read"],
            "allowed_resources": [
                "1a0f385ed98c6af8",
                "1a0f69c169fb928f",
                "1a0f6a90772a743d",
            ],
            "oauth_scopes": ["https://www.googleapis.com/auth/gmail.metadata"],
            "secret_reference": "dufynd_observer_gmail_read_access_token",
            "status": "healthy",
            "expires_at": (checked + timedelta(hours=1)).isoformat(),
            "refreshed_at": (checked - timedelta(minutes=1)).isoformat(),
            "revoked_at": None,
            "last_health_check": checked.isoformat(),
            "health_reason": "healthy",
            "rotation_due_at": None,
        },
    }


def test_broker_health_projection_preserves_activation_and_projects_no_secrets():
    import json

    query(
        "update dufynd_observer_credentials set status='missing_configuration',"
        "health_reason='missing_configuration',expires_at=null,refreshed_at=null,"
        "revoked_at=null,last_health_check=null,rotation_due_at=null,"
        "activation_enabled=(provider='render') returning true"
    )
    health = broker_health_payload()
    projected = query("select project_dufynd_broker_health(%s::jsonb)", (json.dumps(health),))

    assert projected["projected"] == 2
    assert not projected["activation_changed"]
    assert projected["render"]["status"] == "healthy"
    assert projected["gmail"]["status"] == "healthy"
    assert query(
        "select activation_enabled from dufynd_observer_credentials where provider='render'"
    )
    assert not query(
        "select activation_enabled from dufynd_observer_credentials where provider='gmail'"
    )
    assert not query(
        "select capture_dufynd_broker_observation("
        "'gmail_known_threads','gmail:1a0f69c169fb928f','{}')"
    )["accepted"]
    saved = query(
        "select jsonb_object_agg(provider,to_jsonb(c)-'activation_enabled') "
        "from dufynd_observer_credentials c"
    )
    for metadata in saved.values():
        assert "access_token" not in metadata
        assert "refresh_token" not in metadata
        assert "client_secret" not in metadata

    query(
        "update dufynd_observer_credentials set status='missing_configuration',"
        "health_reason='missing_configuration',expires_at=null,refreshed_at=null,"
        "revoked_at=null,last_health_check=null,rotation_due_at=null,"
        "activation_enabled=false returning true"
    )


def test_broker_health_projection_rejects_extra_scope_and_stale_health():
    import json

    import psycopg

    extra = broker_health_payload()
    extra["gmail"]["access_token"] = "must-not-project"
    with pytest.raises(psycopg.errors.RaiseException, match="invalid bounded broker health"):
        query("select project_dufynd_broker_health(%s::jsonb)", (json.dumps(extra),))

    broadened = broker_health_payload()
    broadened["gmail"]["oauth_scopes"] = ["https://www.googleapis.com/auth/gmail.readonly"]
    with pytest.raises(psycopg.errors.RaiseException, match="contract mismatch"):
        query("select project_dufynd_broker_health(%s::jsonb)", (json.dumps(broadened),))

    stale = broker_health_payload(checked_at=datetime.now(UTC) - timedelta(minutes=6))
    with pytest.raises(psycopg.errors.RaiseException, match="stale broker health"):
        query("select project_dufynd_broker_health(%s::jsonb)", (json.dumps(stale),))


@pytest.mark.parametrize(
    "status",
    [
        "missing_configuration",
        "expired",
        "revoked",
        "refresh_failed",
        "scope_mismatch",
        "account_mismatch",
    ],
)
def test_credential_health_fail_closed_and_no_false_human_gate(status):
    query(
        "update dufynd_observer_credentials set status=%s, health_reason=%s, activation_enabled=false where provider='gmail' returning true",
        (status, status),
    )
    health = query("select get_dufynd_credential_health('gmail')")
    assert health["status"] == status
    assert not health["waiting_human_input"]
    assert not query(
        "select capture_dufynd_broker_observation('gmail_known_threads','gmail:1a0f69c169fb928f','{}')"
    )["accepted"]


def test_credential_metadata_exact_contract_and_public_role_denied():
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as c:
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute(
                "update dufynd_observer_credentials set secret_reference='token-canary' where provider='gmail'"
            )
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute(
                "update dufynd_observer_credentials set oauth_scopes='[\"gmail.readonly\"]' where provider='gmail'"
            )
        c.execute("set role anon")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("select * from dufynd_observer_credentials")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("select get_dufynd_credential_health('gmail')")


def test_broker_ingress_exact_source_dedupe_and_no_send():
    import json

    oid = "gmail:1a0f69c169fb928f"
    query("select register_dufynd_observer('gmail','1a0f69c169fb928f')")
    query(
        "update dufynd_observer_credentials set status='healthy',health_reason='healthy',expires_at=now()+interval '1 hour',last_health_check=now(),activation_enabled=true where provider='gmail' returning true"
    )
    evidence = {
        "thread_id": "1a0f69c169fb928f",
        "history_id": "10001",
        "messages": [
            {
                "message_id": "ab123456",
                "thread_id": "1a0f69c169fb928f",
                "internal_date": "1790950000000",
                "sender": "sender@example.com",
                "delivery_failure": False,
            }
        ],
    }
    sql = "select capture_dufynd_broker_observation('gmail_known_threads',%s,%s::jsonb)"
    first = query(sql, (oid, json.dumps(evidence)))
    assert first["inserted"] == 1
    assert query(sql, (oid, json.dumps(evidence)))["inserted"] == 0
    payload = query(
        "select payload->'evidence' from dufynd_jarvis_inbox where source_type='gmail' and payload->'evidence'->>'message_id'='ab123456'"
    )
    assert payload["sender"] == "sender@example.com"
    assert not {"body", "access_token", "refresh_token"} & set(payload)
    import psycopg

    for invalid in (evidence | {"access_token": "canary"}, evidence | {"thread_id": "foreign"}):
        with pytest.raises(psycopg.errors.RaiseException):
            query(sql, (oid, json.dumps(invalid)))
    query(
        "update dufynd_observer_credentials set activation_enabled=false,status='missing_configuration',health_reason='missing_configuration' where provider='gmail' returning true"
    )


@pytest.mark.parametrize("status", ["approval_required", "cancelled"])
def test_recovery_audit_recognizes_known_nonrunning_task_states(status):
    import json

    findings = query(
        "select dufynd_recovery_findings(%s::jsonb,null,now())",
        (
            json.dumps(
                {"status": status, "worker_state": "blocked", "released_at": "2026-10-02T12:00:00Z"}
            ),
        ),
    )
    assert findings == []


def paid_authorization_fixture():
    """Database-only simulation; never installs a real provider or sends a call."""
    import json

    f = fixture()
    decision = f"decision-{uuid4()}"
    approval = {
        "approved": True,
        "scope": "supervisor_v2_bounded_canary",
        "budget_id": f[0],
        "contract_id": f[1],
        "cap_usd": "0.10",
        "per_call_cap_usd": "0.10",
        "max_runs": 20,
    }
    query(
        "update dufynd_provider_contracts set dry_run=false where contract_id=%s returning contract_id",
        (f[1],),
    )
    query(
        "insert into dufynd_human_decisions values(%s,'approved',%s::jsonb) returning decision_id",
        (decision, json.dumps(approval)),
    )
    query(
        "update dufynd_jarvis_budget_windows set reservation_dry_run=false,approved_decision_id=%s where budget_id=%s returning budget_id",
        (decision, f[0]),
    )
    return f, decision


@pytest.mark.parametrize(
    "mutation",
    [
        "approval_revoked",
        "approval_scope_removed",
        "contract_model",
        "contract_dry_run",
        "contract_bound",
        "contract_evidence",
        "worker_state",
        "worker_owner",
        "run_limit",
    ],
)
def test_dispatch_revalidates_current_authorization(mutation):
    f, decision = paid_authorization_fixture()
    admitted = reserve(f)
    assert admitted["allowed"] is True
    if mutation == "approval_revoked":
        query(
            "update dufynd_human_decisions set status='pending' where decision_id=%s returning decision_id",
            (decision,),
        )
    elif mutation == "approval_scope_removed":
        query(
            "update dufynd_human_decisions set decision=decision-'scope' where decision_id=%s returning decision_id",
            (decision,),
        )
    elif mutation.startswith("contract_"):
        assignment = {
            "contract_model": "model='different'",
            "contract_dry_run": "dry_run=true",
            "contract_bound": "max_call_usd=0.11",
            "contract_evidence": 'evidence=\'{"tariff":"changed"}\'',
        }[mutation]
        query(
            f"update dufynd_provider_contracts set {assignment} where contract_id=%s returning contract_id",
            (f[1],),
        )
    elif mutation.startswith("worker_"):
        assignment = (
            "worker_state='queued'" if mutation == "worker_state" else "worker_owner='other'"
        )
        query(
            f"update dufynd_autonomy_tasks set {assignment} where task_id=%s returning task_id",
            (f[2][0][0],),
        )
    else:
        query(
            "update dufynd_jarvis_budget_windows set max_runs=0 where budget_id=%s returning budget_id",
            (f[0],),
        )
    assert (
        query(
            "select dispatch_dufynd_model_call(%s,%s)",
            (admitted["reservation"]["reservation_id"], f[2][0][1]),
        )
        is False
    )
    assert (
        query(
            "select status from dufynd_budget_reservations where reservation_id=%s",
            (admitted["reservation"]["reservation_id"],),
        )
        == "reserved"
    )


def test_dispatch_accepts_exact_run_and_cost_boundary():
    f, _ = paid_authorization_fixture()
    query(
        "update dufynd_jarvis_budget_windows set max_runs=1 where budget_id=%s returning budget_id",
        (f[0],),
    )
    admitted = reserve(f)
    assert admitted["allowed"] is True
    assert (
        query(
            "select dispatch_dufynd_model_call(%s,%s)",
            (admitted["reservation"]["reservation_id"], f[2][0][1]),
        )
        is True
    )


def test_reserve_rejects_incomplete_approval():
    f, decision = paid_authorization_fixture()
    query(
        "update dufynd_human_decisions set decision=decision-'scope' where decision_id=%s returning decision_id",
        (decision,),
    )
    assert reserve(f)["allowed"] is False
