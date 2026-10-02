"""Central exact cost contract. Real candidates stay BOUND_UNKNOWN.

The fixture tokenizer/rates prove orchestration only; they are never a certificate
for an Anthropic or OpenRouter request. No provider is contacted to count tokens.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path

from scripts.dufynd_bounded_provider import BudgetGate

CATALOG = Path(__file__).resolve().parents[1] / "config/dufynd_provider_contracts_v1.json"
BILLING_CLASSES = frozenset(
    {
        "input",
        "output_including_reasoning",
        "cache_read",
        "cache_write_5m",
        "cache_write_1h",
        "server_tool_requests",
        "runtime_ms",
        "request",
    }
)


@dataclass(frozen=True)
class RequestContract:
    contract_id: str
    catalog_version: str
    catalog_digest: str
    provider: str
    model: str
    simulation_only: bool
    max_input_tokens: int
    max_output_tokens: int
    output_includes_reasoning: bool
    hard_output_limit: bool
    input_bound_certified: bool
    unit_price_ceiling_certified: bool
    tokenizer: str
    input_usd_per_token: Decimal | None
    output_usd_per_token: Decimal | None
    expires_at: datetime
    blockers: tuple[str, ...]
    # Every other billable class is prohibited by the strict request shape.
    other_class_limits: tuple[tuple[str, int], ...] = (
        ("cache_read", 0),
        ("cache_write_5m", 0),
        ("cache_write_1h", 0),
        ("server_tool_requests", 0),
        ("runtime_ms", 0),
        ("request", 0),
    )


def load_contract(contract_id: str) -> RequestContract:
    raw = CATALOG.read_bytes()
    catalog = json.loads(raw)
    data = catalog["contracts"].get(contract_id)
    if data is None:
        raise BudgetGate("BOUND_UNKNOWN: unknown_model_or_contract")
    return RequestContract(
        contract_id=contract_id,
        catalog_version=catalog["version"],
        catalog_digest=hashlib.sha256(raw).hexdigest(),
        provider=data["provider"],
        model=data["model"],
        simulation_only=data["simulation_only"],
        max_input_tokens=data["max_input_tokens"],
        max_output_tokens=data["max_output_tokens"],
        output_includes_reasoning=data["output_includes_reasoning"],
        hard_output_limit=data["hard_output_limit"],
        input_bound_certified=data["input_bound_certified"],
        unit_price_ceiling_certified=data["unit_price_ceiling_certified"],
        tokenizer=data["tokenizer"],
        input_usd_per_token=Decimal(data["input_usd_per_token"])
        if data["input_usd_per_token"] is not None
        else None,
        output_usd_per_token=Decimal(data["output_usd_per_token"])
        if data["output_usd_per_token"] is not None
        else None,
        expires_at=datetime.fromisoformat(
            data.get("expires_at", catalog["expires_at"]).replace("Z", "+00:00")
        ),
        blockers=tuple(data["blockers"]),
    )


def calculate_worst_case_cost(contract: RequestContract, *, now: datetime | None = None) -> Decimal:
    """Reserve full permitted input/output, not an estimated expected price."""
    if contract != load_contract(contract.contract_id):
        raise BudgetGate("BOUND_UNKNOWN: altered_or_unknown_model_contract")
    if contract.expires_at <= (now or datetime.now(UTC)):
        raise BudgetGate("BOUND_UNKNOWN: expired_price_contract")
    if (
        contract.blockers
        or not contract.input_bound_certified
        or not contract.unit_price_ceiling_certified
    ):
        raise BudgetGate("BOUND_UNKNOWN: " + ",".join(contract.blockers or ("uncertified_bound",)))
    if not contract.hard_output_limit or not contract.output_includes_reasoning:
        raise BudgetGate("BOUND_UNKNOWN: output_or_reasoning_not_hard_bounded")
    if (
        type(contract.max_input_tokens) is not int
        or type(contract.max_output_tokens) is not int
        or not 0 < contract.max_input_tokens <= 2_000_000
        or not 0 < contract.max_output_tokens <= 2_000_000
    ):
        raise BudgetGate("BOUND_UNKNOWN: token_limit")
    if (
        {k for k, _ in contract.other_class_limits}
        != BILLING_CLASSES - {"input", "output_including_reasoning"}
        or len(contract.other_class_limits) != 6
        or any(type(n) is not int or n != 0 for _, n in contract.other_class_limits)
    ):
        raise BudgetGate("BOUND_UNKNOWN: unbounded_additional_billing_class")
    for price in (contract.input_usd_per_token, contract.output_usd_per_token):
        if (
            not isinstance(price, Decimal)
            or not price.is_finite()
            or not 0 <= price <= 1000
            or price.as_tuple().exponent < -18
        ):
            raise BudgetGate("BOUND_UNKNOWN: missing_or_invalid_price")
    # Limits and decimal scale above keep multiplication exact under this precision.
    with localcontext() as ctx:
        ctx.prec = 64
        return (
            contract.max_input_tokens * contract.input_usd_per_token
            + contract.max_output_tokens * contract.output_usd_per_token
        )


@dataclass(frozen=True)
class BoundedRequest:
    contract: RequestContract
    payload: bytes
    input_tokens: int

    def fingerprint(self) -> str:
        return hashlib.sha256(
            self.contract.catalog_digest.encode()
            + self.contract.contract_id.encode()
            + self.payload
        ).hexdigest()


def count_input_tokens(contract: RequestContract, *, system: str, prompt: str) -> int:
    if not contract.simulation_only or contract.tokenizer != "fixture-utf8-byte-plus-8-v1":
        raise BudgetGate("BOUND_UNKNOWN: no_exact_tokenizer_for_real_provider")
    # This is the definition of the test provider's tokenizer, NOT a Claude estimate.
    return len(system.encode("utf-8")) + len(prompt.encode("utf-8")) + 8


def build_bounded_request(contract: RequestContract, *, system: str, prompt: str) -> BoundedRequest:
    calculate_worst_case_cost(contract)
    if (
        type(system) is not str
        or type(prompt) is not str
        or len(system.encode()) + len(prompt.encode()) > 32768
    ):
        raise BudgetGate("input_limit_exceeded: request_rejected_without_truncation")
    tokens = count_input_tokens(contract, system=system, prompt=prompt)
    if tokens > contract.max_input_tokens:
        raise BudgetGate("input_limit_exceeded: request_rejected_without_truncation")
    body = {
        "model": contract.model,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": contract.max_output_tokens,
        "thinking": {"type": "disabled"},
        "service_tier": "standard_only",
        "inference_geo": "global",
        "stream": False,
    }
    payload = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return BoundedRequest(contract, payload, tokens)


def validate_bounded_request(request: BoundedRequest) -> Decimal:
    # Recompute immutable canonical bytes; reject forged limits, history, tools,
    # stale certificates, mutations, or a count measured on a different request.
    authoritative = load_contract(request.contract.contract_id)
    if authoritative != request.contract:
        raise BudgetGate("BOUND_UNKNOWN: altered_contract")
    try:
        body = json.loads(request.payload)
        rebuilt = build_bounded_request(
            authoritative, system=body["system"], prompt=body["messages"][0]["content"]
        )
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise BudgetGate("BOUND_UNKNOWN: malformed_request") from error
    if rebuilt != request:
        raise BudgetGate("BOUND_UNKNOWN: request_or_token_proof_mismatch")
    return calculate_worst_case_cost(authoritative)


def calculate_actual_cost(
    contract: RequestContract, *, input_tokens: int, output_tokens: int
) -> Decimal:
    calculate_worst_case_cost(contract)
    if (
        type(input_tokens) is not int
        or type(output_tokens) is not int
        or not 0 <= input_tokens <= contract.max_input_tokens
        or not 0 <= output_tokens <= contract.max_output_tokens
    ):
        raise BudgetGate("usage_unknown: actual_count_outside_contract")
    with localcontext() as ctx:
        ctx.prec = 64
        return (
            input_tokens * contract.input_usd_per_token
            + output_tokens * contract.output_usd_per_token
        )
