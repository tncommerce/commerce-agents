"""Single-request Claude cost policy. Margin is conservative, not an exact tokenizer proof.

No request is dispatched without a fresh official tariff, a unique approved
window, a fenced worker and an atomic reservation. No caching/tools/SDK retries.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Any

import httpx
from scripts.dufynd_bounded_provider import BudgetGate

PRICING = Path(__file__).resolve().parents[1] / "config/dufynd_anthropic_nightshift_pricing.json"
CONTRACT_ID = "anthropic-sonnet5-counted-margin-v1"
POLICY = "estimate_margin_v1"
MODEL = "claude-sonnet-5"
MAX_INPUT = 8192
MAX_OUTPUT = 2048
MAX_REQUEST_USD = Decimal("0.036864")
MARGIN = Decimal("1.25")
PADDING = 128
SYSTEM = (
    "You are a DUFYND internal analyst. Produce only an evidence-grounded draft analysis. "
    "No tools, publication, messages, purchases, code changes, owner approvals or final "
    "content approval. Clearly identify missing evidence. Never claim a fact absent from "
    "the supplied snapshot. Your output requires independent verification."
)


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def pricing(now: datetime | None = None) -> dict:
    data = json.loads(PRICING.read_bytes())
    now = now or datetime.now(UTC)
    try:
        verified = datetime.fromisoformat(data["verified_at"])
        expires = datetime.fromisoformat(data["expires_at"])
        if not verified <= now < expires or expires - verified > timedelta(hours=24):
            raise ValueError("stale pricing")
        expected = {
            "input": "2",
            "output": "10",
            "cache_read": "0.20",
            "cache_write_5m": "2.50",
            "cache_write_1h": "4",
        }
        if (
            data["provider"] != "anthropic"
            or data["model"] != MODEL
            or data["contract_id"] != CONTRACT_ID
            or data["rates_usd_per_million"] != expected
            or data["policy"] != POLICY
            or data["estimate_is_exact"] is not False
            or data["margin_multiplier"] != str(MARGIN)
            or data["padding_tokens"] != PADDING
            or data["max_input_tokens"] != MAX_INPUT
            or data["max_output_tokens"] != MAX_OUTPUT
            or Decimal(data["max_request_usd"]) != MAX_REQUEST_USD
            or data["sources"]
            != [
                "https://platform.claude.com/docs/en/about-claude/pricing",
                "https://platform.claude.com/docs/en/models/sonnet-5/overview",
            ]
        ):
            raise ValueError("unknown provider/model/tariff")
    except (KeyError, TypeError, ValueError) as error:
        raise BudgetGate("pricing_contract_unverified_or_expired") from error
    return data


def resolve_budget(bridge) -> tuple[str, dict]:
    data = pricing()
    result = bridge._rpc(
        "resolve_dufynd_nightshift_budget",
        {
            "p_contract_id": CONTRACT_ID,
            "p_pricing_digest": hashlib.sha256(canonical(data)).hexdigest(),
        },
    )
    if not isinstance(result, dict) or result.get("allowed") is not True:
        raise BudgetGate(
            str((result or {}).get("reason", "no_approved_budget"))
            if isinstance(result, dict)
            else "malformed_budget_response"
        )
    status = result["budget"]
    if (
        status.get("can_run") is not True
        or Decimal(str(status["remaining_usd"])) < MAX_REQUEST_USD
        or int(status["remaining_runs"]) < 1
    ):
        raise BudgetGate("budget_exhausted")
    return status["budget_id"], result


@dataclass(frozen=True)
class Prepared:
    payload: bytes
    proof: bytes
    reservation_usd: Decimal

    def fingerprint(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


def prepare(prompt: str, estimate: int, reservation_usd: Decimal = MAX_REQUEST_USD) -> Prepared:
    pricing()
    if (
        type(prompt) is not str
        or len(prompt.encode()) > 32768
        or type(estimate) is not int
        or not 0 <= estimate <= MAX_INPUT
        or not reservation_usd.is_finite()
        or not 0 < reservation_usd <= MAX_REQUEST_USD
    ):
        raise BudgetGate("invalid_count_or_reservation")
    bound = int((Decimal(estimate) * MARGIN).to_integral_value(rounding=ROUND_CEILING)) + PADDING
    input_cost = bound * Decimal("0.000002")
    output = min(
        MAX_OUTPUT,
        int(
            ((reservation_usd - input_cost) / Decimal("0.000010")).to_integral_value(
                rounding=ROUND_FLOOR
            )
        ),
    )
    if bound > MAX_INPUT or output < 1:
        raise BudgetGate("conservative_input_exceeds_reservation")
    body = input_body(prompt) | {
        "max_tokens": output,
        "stream": False,
        "service_tier": "standard_only",
        "inference_geo": "global",
    }
    payload = canonical(body)
    data = pricing()
    proof = {
        "policy": POLICY,
        "estimated_input_tokens": estimate,
        "input_bound_tokens": bound,
        "max_output_tokens": output,
        "margin_multiplier": str(MARGIN),
        "padding_tokens": PADDING,
        "calculated_max_usd": str(input_cost + output * Decimal("0.000010")),
        "request_hash": hashlib.sha256(payload).hexdigest(),
        "count_payload_hash": hashlib.sha256(canonical(input_body(prompt))).hexdigest(),
        "pricing_digest": hashlib.sha256(canonical(data)).hexdigest(),
        "pricing_verified_at": data["verified_at"],
        "counted_at": datetime.now(UTC).isoformat(),
        "estimate_is_exact": False,
    }
    return Prepared(payload, canonical(proof), reservation_usd)


def input_body(prompt: str) -> dict:
    return {
        "model": MODEL,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": prompt}],
        "thinking": {"type": "disabled"},
    }


def validate(prepared: Prepared) -> dict:
    pricing()
    try:
        body, proof = json.loads(prepared.payload), json.loads(prepared.proof)
        prompt = body["messages"][0]["content"]
        rebuilt = prepare(prompt, proof["estimated_input_tokens"], prepared.reservation_usd)
        # counted_at changes; every other proof field and exact payload must match.
        authoritative = json.loads(rebuilt.proof)
        timestamp = datetime.fromisoformat(proof["counted_at"])
        authoritative["counted_at"] = proof["counted_at"]
        if (
            rebuilt.payload != prepared.payload
            or authoritative != proof
            or not timedelta(0) <= datetime.now(UTC) - timestamp <= timedelta(seconds=120)
        ):
            raise ValueError("changed/expired request")
    except (KeyError, ValueError, TypeError, IndexError) as error:
        raise BudgetGate("request_proof_mismatch") from error
    return proof


def actual_usage(prepared: Prepared, response: dict) -> tuple[Decimal, dict, bool]:
    """Retain actual billing even when it exceeds the margin; never clamp evidence."""
    proof = json.loads(prepared.proof)
    if (
        response.get("model") != MODEL
        or not isinstance(response.get("id"), str)
        or not response["id"]
    ):
        raise BudgetGate("unknown_provider_receipt")
    usage = response.get("usage")
    if not isinstance(usage, dict) or not {"input_tokens", "output_tokens"} <= usage.keys():
        raise BudgetGate("missing_usage")
    allowed = {
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "cache_creation",
        "output_tokens_details",
        "server_tool_use",
        "service_tier",
        "inference_geo",
    }
    if usage.keys() - allowed:
        raise BudgetGate("unknown_billing_class")
    for key in (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    ):
        if type(usage.get(key, 0)) is not int or usage.get(key, 0) < 0:
            raise BudgetGate("invalid_usage")
    if usage.get("cache_creation_input_tokens", 0) or usage.get("cache_read_input_tokens", 0):
        raise BudgetGate("unexpected_cache_usage")
    for key in ("cache_creation", "server_tool_use"):
        detail = usage.get(key) or {}
        if not isinstance(detail, dict) or any(
            type(v) is not int or v != 0 for v in detail.values()
        ):
            raise BudgetGate("unexpected_additional_charge")
    if (
        usage.get("service_tier", "standard") != "standard"
        or usage.get("inference_geo", "global") != "global"
    ):
        raise BudgetGate("unexpected_pricing_tier")
    thinking = (usage.get("output_tokens_details") or {}).get("thinking_tokens", 0)
    if type(thinking) is not int or not 0 <= thinking <= usage["output_tokens"]:
        raise BudgetGate("invalid_thinking_usage")
    cost = usage["input_tokens"] * Decimal("0.000002") + usage["output_tokens"] * Decimal(
        "0.000010"
    )
    violated = (
        usage["input_tokens"] > proof["input_bound_tokens"]
        or usage["output_tokens"] > proof["max_output_tokens"]
        or cost > prepared.reservation_usd
    )
    return (
        cost,
        {
            "provider": "anthropic",
            "model": MODEL,
            "provider_request_id": response["id"],
            "usage": usage,
            "calculated_actual_usd": str(cost),
            "pre_request": proof,
            "reservation_usd": str(prepared.reservation_usd),
            "policy_violation": violated,
        },
        violated,
    )


class CountedClient:
    def __init__(self, api_key: str, *, transport: httpx.BaseTransport | None = None):
        if not api_key:
            raise BudgetGate("provider_credential_missing")
        self.api_key, self.transport = api_key, transport

    def _post(self, path: str, payload: bytes) -> dict:
        # Fixed endpoint, no redirects, SDK, retries, beta headers or paid tools.
        with httpx.Client(
            transport=self.transport, timeout=60, follow_redirects=False, trust_env=False
        ) as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages" + path,
                content=payload,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
            )
            response.raise_for_status()
            return response.json()

    def count(self, prompt: str) -> int:
        if type(prompt) is not str or len(prompt.encode()) > 32768:
            raise BudgetGate("input_payload_too_large")
        pricing()
        count = self._post("/count_tokens", canonical(input_body(prompt))).get("input_tokens")
        if type(count) is not int or not 0 <= count <= MAX_INPUT:
            raise BudgetGate("invalid_count_tokens_response")
        return count

    def execute(self, bridge, prepared: Prepared, *, task: dict, budget_id: str, key: str) -> dict:
        proof = validate(prepared)
        if resolve_budget(bridge)[0] != budget_id:
            raise BudgetGate("budget_window_changed")
        admission = bridge.reserve_model_call(
            budget_id=budget_id,
            task_id=task["task_id"],
            owner=task["worker_owner"],
            lease_token=task["lease_token"],
            idempotency_key=key,
            request_hash=prepared.fingerprint(),
            contract_id=CONTRACT_ID,
            max_usd=str(prepared.reservation_usd),
            ttl_seconds=180,
        )
        if not isinstance(admission, dict) or admission.get("allowed") is not True:
            raise BudgetGate("reservation_denied")
        rid = admission["reservation"]["reservation_id"]
        if (
            bridge._rpc(
                "dispatch_dufynd_counted_call",
                {"p_reservation_id": rid, "p_lease_token": task["lease_token"], "p_proof": proof},
            )
            is not True
        ):
            raise BudgetGate("dispatch_denied")
        response = None
        try:
            response = self._post("", prepared.payload)
            cost, evidence, violation = actual_usage(prepared, response)
        except BaseException as error:
            # One dispatched request, never an automatic retry. Unknown billing pauses the window.
            bridge._rpc(
                "settle_dufynd_counted_call",
                {
                    "p_reservation_id": rid,
                    "p_lease_token": task["lease_token"],
                    "p_actual_usd": None,
                    "p_evidence": {
                        "unknown_cost": True,
                        "error_type": type(error).__name__,
                        "provider": "anthropic",
                        "model": MODEL,
                        "provider_request_id": response.get("id")
                        if isinstance(response, dict)
                        else None,
                        "usage": response.get("usage") if isinstance(response, dict) else None,
                    },
                    "p_violation": True,
                },
            )
            raise BudgetGate("provider_outcome_unknown_no_retry") from error
        if (
            bridge._rpc(
                "settle_dufynd_counted_call",
                {
                    "p_reservation_id": rid,
                    "p_lease_token": task["lease_token"],
                    "p_actual_usd": str(cost),
                    "p_evidence": evidence,
                    "p_violation": violation,
                },
            )
            is not True
        ):
            raise BudgetGate("settlement_pending_watchdog_no_retry")
        if violation:
            raise BudgetGate("provider_usage_exceeded_conservative_policy")
        remaining = bridge.load_budget_status(budget_id)
        return {
            "response": response,
            "reservation_id": rid,
            "cost_usd": str(cost),
            "budget_id": budget_id,
            "evidence": evidence,
            "remaining_budget": remaining,
        }


async def process_counted_task(bridge, *, task_id: str | None = None) -> int:
    import asyncio

    from scripts.dufynd_jarvis_runtime import _is_green_autonomy_task

    budget_id, _ = resolve_budget(bridge)
    queue = bridge.load_autonomy_queue()
    tasks = [
        t
        for t in queue.get("safe_to_execute", [])
        if _is_green_autonomy_task(t)
        and t.get("domain") in ("research", "content")
        and (not task_id or t["task_id"] == task_id)
    ]
    if not tasks:
        return 0
    task = bridge.claim_worker(tasks[0]["task_id"], "anthropic-counted-nightshift-v1")
    if task is None:
        return 0
    task_id = task["task_id"]
    try:
        # Fixed public repository inputs, never arbitrary files, credentials or executable tools.
        snapshot = {
            k: task.get(k) for k in ("task_id", "title", "instruction", "domain", "dependencies")
        }
        paths = {
            "research": ["examples/retail/storefront-web/lib/analytics.ts"],
            "content": [
                "examples/retail/data/dufynd_content_strategy.json",
                "examples/retail/data/dufynd_high_end_launch_assets.json",
            ],
        }[task["domain"]]
        snapshot["repository_evidence"] = []
        root = Path(__file__).resolve().parents[1]
        for name in paths:
            raw = (root / name).read_bytes()
            snapshot["repository_evidence"].append(
                {
                    "path": name,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "text": raw.decode()[:6000],
                    "truncated": len(raw.decode()) > 6000,
                }
            )
        snapshot["head"] = os.getenv("GITHUB_SHA")
        snapshot["context_scope"] = (
            "Bounded repository snapshot; not live product, social or revenue evidence."
        )
        prompt = canonical(snapshot).decode()
        client = CountedClient(os.getenv("ANTHROPIC_API_KEY", ""))
        estimate = await asyncio.to_thread(client.count, prompt)
        prepared = prepare(prompt, estimate)
        result = await asyncio.to_thread(
            client.execute,
            bridge,
            prepared,
            task=task,
            budget_id=budget_id,
            key=f"{task_id}:{task['lease_token']}",
        )
        blocks = result["response"].get("content") or []
        text = "\n".join(b["text"] for b in blocks if b.get("type") == "text")
        bridge.record_run(
            run_type=f"safe_task:{task_id}",
            input_summary=prompt[:4000],
            output_summary=text[:8000],
            decisions=[
                result
                | {
                    "response": None,
                    "github_run_id": os.getenv("GITHUB_RUN_ID"),
                    "github_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
                    "head_sha": os.getenv("GITHUB_SHA"),
                }
            ],
            agent_name="jarvis",
        )
        # Maker cannot mark its own task/content done. Release the lease for independent review.
        bridge.update_worker(
            task_id,
            "blocked",
            reason="independent_verification_required",
            evidence=text[:11000]
            + "\nDUFYND_TASK_STATE: blocked\nIndependent verification required; no final approval.",
        )
        return 0
    except Exception as error:
        bridge.update_worker(
            task_id,
            "blocked",
            reason="counted_worker_failed_no_retry",
            evidence=f"Counted worker stopped: {type(error).__name__}; no retry.\nDUFYND_TASK_STATE: blocked",
        )
        return 1
