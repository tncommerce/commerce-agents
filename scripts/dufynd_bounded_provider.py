"""Single-call reservation adapter. Exposes deterministic fake/mock providers only.

No SDK loop, automatic retry, network transport or environment switch can turn
this module into paid execution. A paid transport and certified tariff/envelope
need a subsequent review AND a new budget-specific owner approval.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol


class BudgetGate(RuntimeError):
    """Task-local pause; never a human-input gate or supervisor termination."""


class ReservationStore(Protocol):
    def reserve_model_call(self, **payload: Any) -> dict[str, Any]: ...
    def dispatch_model_call(self, reservation_id: str, lease_token: str) -> bool: ...
    def settle_model_call(
        self, reservation_id: str, lease_token: str, actual_usd: str, evidence: dict[str, Any]
    ) -> bool: ...
    def update_worker(self, task_id: str, state: str, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class CallEnvelope:
    prompt: str
    max_output_tokens: int = 256

    def fingerprint(self) -> str:
        payload = json.dumps(
            {"prompt": self.prompt, "max_output_tokens": self.max_output_tokens},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class ProviderResult:
    text: str
    cost_usd: Decimal
    request_id: str
    usage_evidence: dict[str, Any] | None = None


@dataclass(frozen=True)
class BoundCertificate:
    contract_id: str
    maximum_usd: Decimal
    max_input_bytes: int = 4096
    max_output_tokens: int = 256

    def validate(self, request: CallEnvelope) -> Decimal:
        amount = self.maximum_usd
        if (
            not isinstance(amount, Decimal)
            or not amount.is_finite()
            or amount <= 0
            or self.max_input_bytes <= 0
            or self.max_output_tokens <= 0
            or len(request.prompt.encode()) > self.max_input_bytes
            or not isinstance(request.max_output_tokens, int)
            or not 0 < request.max_output_tokens <= self.max_output_tokens
        ):
            raise BudgetGate("unbounded_provider_cost")
        return amount


class FakeBoundedProvider:
    """Non-network provider for tests/replay; its bound is mechanically enforced."""

    def __init__(self, certificate: BoundCertificate, *, cost_usd: Decimal, fail: bool = False):
        self.certificate = certificate
        self.cost_usd = cost_usd
        self.fail = fail
        self.calls = 0

    def call(self, request: CallEnvelope) -> ProviderResult:
        maximum = self.certificate.validate(request)
        self.calls += 1
        if self.fail:
            raise RuntimeError("simulated provider response loss")
        if not self.cost_usd.is_finite() or not 0 <= self.cost_usd <= maximum:
            raise RuntimeError("provider bound violated")
        return ProviderResult("deterministic fake result", self.cost_usd, f"fake-{self.calls}")


class BoundedProviderAdapter:
    def __init__(self, store: ReservationStore, provider: Any):
        # Exact class prevents a subclass replacing the no-network fake contract.
        from scripts.dufynd_messages_transport import SimulatedMessagesProvider

        if type(provider) not in (FakeBoundedProvider, SimulatedMessagesProvider):
            raise BudgetGate("paid_canary_requires_new_owner_approval_and_certified_transport")
        self.store = store
        self.provider = provider

    def execute(
        self,
        request: Any,
        *,
        budget_id: str,
        task_id: str,
        worker_owner: str,
        lease_token: str,
        idempotency_key: str,
    ) -> ProviderResult:
        try:
            maximum = self.provider.certificate.validate(request)
            admission = self.store.reserve_model_call(
                budget_id=budget_id,
                task_id=task_id,
                owner=worker_owner,
                lease_token=lease_token,
                idempotency_key=idempotency_key,
                request_hash=request.fingerprint(),
                contract_id=self.provider.certificate.contract_id,
                max_usd=str(maximum),
                ttl_seconds=180,
            )
            if not admission.get("allowed"):
                raise BudgetGate(str(admission.get("reason") or "reservation_denied"))
            reservation_id = admission["reservation"]["reservation_id"]
            # Repeated reserve is safe; only the unique dispatch winner may call.
            # An ambiguous RPC response MUST NOT cause an unreserved retry.
            if not self.store.dispatch_model_call(reservation_id, lease_token):
                raise BudgetGate("dispatch_denied_or_already_dispatched")
        except BudgetGate as error:
            self.store.update_worker(
                task_id, "queued", reason=str(error), evidence=f"Budget adapter: {error}"
            )
            raise
        try:
            result = self.provider.call(request)
            if not result.cost_usd.is_finite() or not 0 <= result.cost_usd <= maximum:
                raise RuntimeError("provider bound violated")
        except BaseException:
            # Even transport errors can have incurred billing. Charge the full
            # reservation, including cancellation, instead of assuming zero.
            # If persistence fails, TTL performs the same deterministic charge.
            self.store.settle_model_call(
                reservation_id,
                lease_token,
                str(maximum),
                {"rule": "ambiguous_failure_charge_max", "dry_run": True},
            )
            raise
        if not self.store.settle_model_call(
            reservation_id,
            lease_token,
            str(result.cost_usd),
            {
                "provider_request_id": result.request_id,
                "dry_run": True,
                "request_hash": request.fingerprint(),
                "rule": "verified_actual_cost",
                "bound_and_usage": result.usage_evidence,
            },
        ):
            raise BudgetGate("settlement_pending_watchdog_recovery")
        return result
