"""Independent checker contract. No live provider adapter or automatic paid retry.

Semantic checking must be performed by an independently authenticated checker.
This module validates its handoff/receipt; it does not manufacture acceptance.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from scripts.dufynd_worker_evidence import encode

OUTCOMES = frozenset(
    {
        "accepted",
        "verified",
        "needs_more_evidence",
        "rework_required",
        "waiting_external",
        "waiting_human_input",
        "blocked",
    }
)
CHECKS = frozenset(
    {
        "fact_fidelity",
        "unsupported_claims",
        "hallucinations",
        "completeness",
        "task_scope",
        "safety",
        "spend",
        "publishing",
        "external_actions",
        "evidence_coverage",
    }
)
MAX_REWORK = 1


@dataclass(frozen=True)
class CheckerIdentity:
    # Set by trusted host authentication, never read from the model response.
    principal: str
    paid: bool = False


class Checker(Protocol):
    def review(self, handoff: dict) -> dict: ...


def make_handoff(
    task: dict,
    maker_result: str,
    evidence: dict,
    *,
    maker: str,
    runtime: dict | None = None,
    attempt: int = 0,
) -> dict:
    if not maker or not 0 <= attempt <= MAX_REWORK or len(maker_result.encode()) > 12000:
        raise ValueError("invalid_checker_handoff")
    packet = {
        "version": 1,
        "task": task,
        "maker": maker,
        "maker_result": maker_result,
        "evidence": evidence,
        "runtime": runtime or {},
        "rework_count": attempt,
        "required_checks": sorted(CHECKS),
        "automatic_paid_retry": False,
    }
    if len(encode(packet)) > 49152:
        raise ValueError("checker_context_limit")
    packet["handoff_sha256"] = hashlib.sha256(encode(packet)).hexdigest()
    return packet


def verify_receipt(handoff: dict, receipt: dict, *, identity: CheckerIdentity) -> dict:
    body = {k: v for k, v in handoff.items() if k != "handoff_sha256"}
    digest = hashlib.sha256(encode(body)).hexdigest()
    if (
        digest != handoff.get("handoff_sha256")
        or not identity.principal
        or identity.principal == handoff["maker"]
    ):
        raise ValueError("independent_checker_required")
    if receipt.get("handoff_sha256") != digest or receipt.get("outcome") not in OUTCOMES:
        raise ValueError("checker_receipt_mismatch")
    checks = receipt.get("checks")
    if (
        not isinstance(checks, dict)
        or set(checks) != CHECKS
        or any(type(v) is not bool for v in checks.values())
    ):
        raise ValueError("incomplete_checker_checks")
    required_evidence = receipt.get("additional_evidence")
    if not isinstance(required_evidence, list) or any(
        not isinstance(v, str) for v in required_evidence
    ):
        raise ValueError("invalid_evidence_request")
    outcome = receipt["outcome"]
    if outcome in {"accepted", "verified"} and (not all(checks.values()) or required_evidence):
        raise ValueError("acceptance_without_complete_verification")
    task = handoff["task"]
    if outcome in {"accepted", "verified"} and task.get("requires_human_approval"):
        outcome = "waiting_human_input"
    if outcome == "rework_required" and handoff["rework_count"] >= MAX_REWORK:
        outcome = "blocked"
    decision = {
        "version": 1,
        "task_id": task["task_id"],
        "maker": handoff["maker"],
        "packet_sha256": handoff["evidence"].get("packet_sha256"),
        "checks": checks,
        "runtime": handoff["runtime"],
        "outcome": outcome,
        "checker": identity.principal,
        "handoff_sha256": digest,
        "automatic_paid_retry": False,
        "owner_publish_allowed": False,
        "additional_evidence": required_evidence,
        "next_state": {
            "accepted": "done",
            "verified": "done",
            "needs_more_evidence": "blocked",
            "rework_required": "blocked",
        }.get(outcome, outcome),
    }

    decision["receipt_sha256"] = hashlib.sha256(encode(decision)).hexdigest()
    return decision


def run_checker(
    handoff: dict,
    checker: Checker,
    *,
    identity: CheckerIdentity,
    owner_budget_authorized: bool = False,
) -> dict:
    if identity.principal == handoff["maker"]:
        raise ValueError("independent_checker_required")
    if identity.paid and not owner_budget_authorized:
        raise ValueError("paid_checker_requires_new_owner_budget")
    # Exactly one invocation. No retries, no queue mutation, no publication.
    return verify_receipt(handoff, checker.review(handoff), identity=identity)


def next_safe_task(tasks: list[dict], verified_task_id: str, decision: dict) -> dict | None:
    """Pure scheduling proposal; trusted control-plane must persist/verify before dispatch."""
    receipt_body = {k: v for k, v in decision.items() if k != "receipt_sha256"}
    if (
        decision.get("next_state") != "done"
        or decision.get("task_id") != verified_task_id
        or not decision.get("checker")
        or decision.get("checker") == decision.get("maker")
        or decision.get("outcome") not in {"accepted", "verified"}
        or decision.get("receipt_sha256") != hashlib.sha256(encode(receipt_body)).hexdigest()
    ):
        return None
    candidates = [
        t
        for t in tasks
        if t["task_id"] != verified_task_id
        and t.get("status") == "ready"
        and not t.get("requires_human_approval")
        and t.get("approval_action_type", "auto_allowed") == "auto_allowed"
        and not t.get("provider_cost_unknown")
        and all(
            d == verified_task_id
            or any(x["task_id"] == d and x.get("status") == "done" for x in tasks)
            for d in t.get("dependencies", [])
        )
    ]
    return (
        min(candidates, key=lambda t: (-int(t.get("priority") or 0), t["task_id"]))
        if candidates
        else None
    )
