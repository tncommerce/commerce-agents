"""Prepared direct Anthropic HTTP transport, exclusively exercised through mocks.

There is no network client factory here. Phase 2A.2 does not certify a production
provider: all real contracts are BOUND_UNKNOWN. No environment flag can authorize
network execution or replace missing input/rate guarantees.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

import httpx
from scripts.dufynd_bounded_provider import BudgetGate, ProviderResult
from scripts.dufynd_provider_contract import (
    BoundedRequest,
    RequestContract,
    calculate_worst_case_cost,
    validate_bounded_request,
)

ENDPOINT = "https://api.anthropic.com/v1/messages"


@dataclass(frozen=True)
class RequestCertificate:
    contract: RequestContract
    contract_id: str = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "contract_id", self.contract.contract_id)

    def validate(self, request: BoundedRequest) -> Decimal:
        if request.contract != self.contract:
            raise BudgetGate("BOUND_UNKNOWN: certificate_request_mismatch")
        return validate_bounded_request(request)


def prepare_http_request(request: BoundedRequest, *, api_key: str) -> httpx.Request:
    validate_bounded_request(request)
    return httpx.Request(
        "POST",
        ENDPOINT,
        content=request.payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )


def settle_usage(request: BoundedRequest, response: dict) -> tuple[Decimal, dict]:
    """Validate every billed class; missing or unexpected usage charges the bound."""
    maximum = validate_bounded_request(request)
    if response.get("model") != request.contract.model or not response.get("id"):
        raise BudgetGate("usage_unknown: model_or_receipt_missing")
    usage = response.get("usage")
    if not isinstance(usage, dict) or not {"input_tokens", "output_tokens"} <= usage.keys():
        raise BudgetGate("usage_unknown: missing_usage")
    allowed = {
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "output_tokens_details",
    }
    if usage.keys() - allowed:
        raise BudgetGate("usage_unknown: unexpected_billing_class")
    for name in allowed - {"output_tokens_details"}:
        value = usage.get(name, 0)
        if type(value) is not int or value < 0:
            raise BudgetGate("usage_unknown: invalid_token_count")
    if usage.get("cache_creation_input_tokens", 0) or usage.get("cache_read_input_tokens", 0):
        raise BudgetGate("usage_unknown: forbidden_cache_charge")
    i, o = usage["input_tokens"], usage["output_tokens"]
    if (
        i != request.input_tokens
        or i > request.contract.max_input_tokens
        or o > request.contract.max_output_tokens
    ):
        raise BudgetGate("usage_unknown: input_or_output_bound_violation")
    details = usage.get("output_tokens_details", {})
    if not isinstance(details, dict) or details.keys() - {"thinking_tokens"}:
        raise BudgetGate("usage_unknown: additional_reasoning_class")
    thinking = details.get("thinking_tokens", 0)
    if type(thinking) is not int or not 0 <= thinking <= o:
        raise BudgetGate("usage_unknown: reasoning_outside_output_bound")
    # Keep all price arithmetic in the same central contract function. Actual
    # usage is its second, explicit path; no provider-supplied USD is trusted.
    from scripts.dufynd_provider_contract import calculate_actual_cost

    actual = calculate_actual_cost(request.contract, input_tokens=i, output_tokens=o)
    if actual > maximum:
        raise BudgetGate("usage_unknown: calculated_cost_exceeds_reservation")
    return actual, {
        "usage": usage,
        "catalog_version": request.contract.catalog_version,
        "catalog_digest": request.contract.catalog_digest,
        "input_tokens_pre_dispatch": request.input_tokens,
        "worst_case_cost_usd": str(maximum),
        "request_hash": request.fingerprint(),
    }


class SimulatedMessagesProvider:
    """Real HTTP framing/parser with an in-process mock, never socket transport."""

    def __init__(self, contract: RequestContract, transport: httpx.MockTransport):
        calculate_worst_case_cost(contract)
        if not contract.simulation_only or type(transport) is not httpx.MockTransport:
            raise BudgetGate("paid_transport_disabled_pending_certification_and_new_owner_budget")
        self.certificate = RequestCertificate(contract)
        self.transport = transport
        self.calls = 0

    def call(self, request: BoundedRequest) -> ProviderResult:
        self.certificate.validate(request)
        if type(self.transport) is not httpx.MockTransport:
            raise BudgetGate("paid_transport_disabled_pending_certification_and_new_owner_budget")
        prepared = prepare_http_request(request, api_key="offline-fixture-key")
        # Single send, no redirects, no SDK retries, no account defaults/history.
        with httpx.Client(
            transport=self.transport, timeout=15, follow_redirects=False, trust_env=False
        ) as client:
            self.calls += 1
            response = client.send(prepared)
            response.raise_for_status()
            payload = response.json()
        actual, evidence = settle_usage(request, payload)
        content = payload.get("content", [])
        if not isinstance(content, list) or any(
            not isinstance(b, dict) or b.get("type") != "text" or type(b.get("text")) is not str
            for b in content
        ):
            raise BudgetGate("usage_unknown: unexpected_tool_or_content_block")
        return ProviderResult(
            "\n".join(b["text"] for b in content), actual, payload["id"], evidence
        )
