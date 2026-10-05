"""Owner action mutations for the private DUFYND Control Room.

This module intentionally supports only narrow human-decision transitions. It never
publishes content, changes social profiles, spends money, merges code or bypasses
existing worker gates.
"""

from __future__ import annotations

import hmac
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from .jarvis_dashboard import PROJECT_ORIGIN


class OwnerActionUnavailable(RuntimeError):
    pass


class OwnerActionConflict(RuntimeError):
    pass


class OwnerActionWriter:
    def __init__(self, *, secret_key: str, transport: httpx.BaseTransport | None = None) -> None:
        if not secret_key:
            raise OwnerActionUnavailable()
        self._secret_key = secret_key
        self._transport = transport

    def _headers(self, *, representation: bool = False) -> dict[str, str]:
        headers = {"apikey": self._secret_key}
        if self._secret_key.startswith("eyJ"):
            headers["Authorization"] = "Bearer " + self._secret_key
        if representation:
            headers["Prefer"] = "return=representation"
        return headers

    @staticmethod
    def _validate_identity(decision_id: object, action_token: object) -> tuple[str, str]:
        if not isinstance(decision_id, str) or not re.fullmatch(
            r"[A-Za-z0-9._:-]{1,180}", decision_id
        ):
            raise ValueError("invalid_decision_id")
        if not isinstance(action_token, str) or not re.fullmatch(
            r"[A-Z][A-Z0-9_-]{2,180}", action_token
        ):
            raise ValueError("invalid_action_token")
        return decision_id, action_token

    def _load_pending(self, decision_id: str) -> dict[str, Any]:
        try:
            with httpx.Client(
                transport=self._transport,
                timeout=5,
                follow_redirects=False,
            ) as client:
                response = client.get(
                    PROJECT_ORIGIN + "/rest/v1/dufynd_human_decisions",
                    headers=self._headers(),
                    params={
                        "select": "decision_id,action_type,status,decision_token,context,decision",
                        "decision_id": "eq." + decision_id,
                        "status": "eq.pending",
                        "limit": "1",
                    },
                )
        except httpx.HTTPError:
            raise OwnerActionUnavailable() from None
        if response.status_code != 200 or len(response.content) > 100_000:
            raise OwnerActionUnavailable()
        payload = response.json()
        if not isinstance(payload, list) or len(payload) > 1:
            raise OwnerActionUnavailable()
        if not payload:
            raise OwnerActionConflict()
        row = payload[0]
        if not isinstance(row, dict):
            raise OwnerActionUnavailable()
        return row

    def resolve(
        self,
        *,
        decision_id: object,
        action_token: object,
        action: object,
    ) -> dict[str, Any]:
        decision_id, action_token = self._validate_identity(decision_id, action_token)
        if action not in {"approve", "approve_review", "confirm_manual"}:
            raise ValueError("invalid_owner_action")

        row = self._load_pending(decision_id)
        expected = row.get("decision_token")
        if not isinstance(expected, str) or not hmac.compare_digest(expected, action_token):
            raise OwnerActionConflict()

        context = row.get("context")
        if not isinstance(context, dict):
            raise OwnerActionConflict()

        manual = context.get("manual_action_required") is True
        direct = context.get("approval_alone_enables_execution") is True
        if action == "confirm_manual" and not manual:
            raise OwnerActionConflict()
        if action == "approve" and not direct:
            raise OwnerActionConflict()
        if action == "approve_review" and (
            manual
            or row.get("action_type") not in {"content_candidate_review", "image_visual_review"}
        ):
            raise OwnerActionConflict()

        now = datetime.now(UTC).isoformat()
        decision = {
            "source": "private_control_room",
            "owner_confirmed": True,
            "action": action,
            "confirmed_at": now,
            "owner_confirmed_manual_action": action == "confirm_manual",
            "verification_required": False,
            "review_only": action == "approve_review",
            "owner_action_completed": action == "confirm_manual",
            "verification_basis": "owner_confirmation" if action == "confirm_manual" else None,
        }
        patch = {
            "decision": decision,
            "decided_at": now,
        }
        if action in {"approve", "approve_review"}:
            patch["status"] = "approved"
        elif action == "confirm_manual":
            patch["status"] = "completed"
            patch["completed_at"] = now

        try:
            with httpx.Client(
                transport=self._transport,
                timeout=5,
                follow_redirects=False,
            ) as client:
                response = client.patch(
                    PROJECT_ORIGIN + "/rest/v1/dufynd_human_decisions",
                    headers=self._headers(representation=True),
                    params={
                        "decision_id": "eq." + decision_id,
                        "status": "eq.pending",
                        "decision_token": "eq." + action_token,
                    },
                    json=patch,
                )
        except httpx.HTTPError:
            raise OwnerActionUnavailable() from None
        if response.status_code not in {200, 204} or len(response.content) > 100_000:
            raise OwnerActionUnavailable()
        payload = response.json() if response.content else []
        if not isinstance(payload, list):
            raise OwnerActionUnavailable()
        if not payload:
            raise OwnerActionConflict()
        saved = payload[0]
        if not isinstance(saved, dict):
            raise OwnerActionUnavailable()
        return {
            "ok": True,
            "decision_id": decision_id,
            "action": action,
            "status": saved.get("status"),
            "verification_required": False,
        }
