"""Narrow safe-action bridge for the private DUFYND Jarvis voice interface.

Only the existing certified Thin V1 free orchestrator can be invoked. The backend
cannot publish, spend, merge main, send outbound messages, or bypass owner gates.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx

from .jarvis_dashboard import PROJECT_ORIGIN


class JarvisSafeActionUnavailable(RuntimeError):
    pass


class JarvisSafeActionConflict(RuntimeError):
    pass


class JarvisSafeActionRunner:
    """Invoke only the certified zero-spend Thin V1 orchestration RPC."""

    def __init__(self, *, secret_key: str, transport: httpx.BaseTransport | None = None) -> None:
        if not secret_key:
            raise JarvisSafeActionUnavailable()
        self._secret_key = secret_key
        self._transport = transport
        self._attempts: list[float] = []
        self._lock = threading.Lock()

    def _headers(self) -> dict[str, str]:
        headers = {
            "apikey": self._secret_key,
            "Content-Type": "application/json",
        }
        if self._secret_key.startswith("eyJ"):
            headers["Authorization"] = "Bearer " + self._secret_key
        return headers

    def _check_attempt(self) -> None:
        with self._lock:
            now = time.monotonic()
            self._attempts = [value for value in self._attempts if now - value < 600]
            if len(self._attempts) >= 8:
                raise JarvisSafeActionConflict("safe_action_rate_limited")
            self._attempts.append(now)

    @staticmethod
    def _sanitize_gate(value: object) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        return {
            "decision_id": value.get("decision_id"),
            "action_type": value.get("action_type"),
        }

    @classmethod
    def _sanitize(cls, payload: dict[str, Any]) -> dict[str, Any]:
        completed = payload.get("completed")
        queue_counts = payload.get("queue_counts")
        gates = payload.get("pending_owner_gates")
        result = {
            "ok": True,
            "source": "dufynd_thin_v1_certified_free_orchestrator",
            "stop_reason": payload.get("stop_reason"),
            "paid_calls": payload.get("paid_calls"),
            "new_spend_usd": payload.get("new_spend_usd"),
            "completed": completed if isinstance(completed, list) else [],
            "queue_counts": queue_counts if isinstance(queue_counts, dict) else {},
            "pending_owner_gates": [
                gate
                for gate in (cls._sanitize_gate(item) for item in (gates or []))
                if gate is not None
            ][:12],
            "active_leases": payload.get("active_leases"),
            "stale_leases": payload.get("stale_leases"),
            "provider_cost_unknown": payload.get("provider_cost_unknown"),
            "limitations": payload.get("limitations"),
        }
        ci = payload.get("loop_ci")
        if isinstance(ci, dict):
            result["ci"] = {
                "ready": ci.get("ready"),
                "reason": ci.get("reason"),
                "status": ci.get("status"),
                "conclusion": ci.get("conclusion"),
                "sha": ci.get("sha"),
            }
        return result

    def advance_next_safe_work(self) -> dict[str, Any]:
        self._check_attempt()
        try:
            with httpx.Client(
                transport=self._transport,
                timeout=10,
                follow_redirects=False,
            ) as client:
                response = client.post(
                    PROJECT_ORIGIN + "/rest/v1/rpc/run_dufynd_thin_v1",
                    headers=self._headers(),
                    json={},
                )
        except httpx.HTTPError:
            raise JarvisSafeActionUnavailable() from None

        if response.status_code != 200 or len(response.content) > 250_000:
            raise JarvisSafeActionUnavailable()

        payload = response.json()
        if not isinstance(payload, dict):
            raise JarvisSafeActionUnavailable()

        if payload.get("paid_calls") not in {0, None}:
            raise JarvisSafeActionConflict("paid_call_detected")
        if payload.get("new_spend_usd") not in {0, 0.0, None}:
            raise JarvisSafeActionConflict("spend_detected")
        if payload.get("owner_gate_action_executed") not in {False, None}:
            raise JarvisSafeActionConflict("owner_gate_execution_detected")

        return self._sanitize(payload)
