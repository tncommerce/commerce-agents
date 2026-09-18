from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ValidationError

from .merchant_run_reports import MerchantImportRunReport


class MerchantMachineResult(BaseModel):
    status: Literal["ok", "review"]
    exit_code: int
    reasons: list[str]
    run: MerchantImportRunReport


class MerchantAutomationDecision(BaseModel):
    action: Literal["continue", "hold"]
    exit_code: int
    reasons: list[str]
    run_id: str | None = None


def decide_automation(payload: dict) -> MerchantAutomationDecision:
    try:
        result = MerchantMachineResult.model_validate(payload)
    except ValidationError:
        return MerchantAutomationDecision(
            action="hold",
            exit_code=20,
            reasons=["invalid_machine_result"],
        )

    if result.status == "ok" and result.exit_code == 0:
        return MerchantAutomationDecision(
            action="continue",
            exit_code=0,
            reasons=[],
            run_id=result.run.run_id,
        )

    if result.status == "review" and result.exit_code == 10:
        return MerchantAutomationDecision(
            action="hold",
            exit_code=10,
            reasons=result.reasons or ["review_required"],
            run_id=result.run.run_id,
        )

    return MerchantAutomationDecision(
        action="hold",
        exit_code=20,
        reasons=["inconsistent_machine_result"],
        run_id=result.run.run_id,
    )
