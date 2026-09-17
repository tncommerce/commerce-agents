from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .merchant_run_reports import MerchantImportRunReport


class MerchantOperationalStatus(BaseModel):
    status: Literal["ok", "review"]
    exit_code: int
    reasons: list[str]


def evaluate_import_run(
    report: MerchantImportRunReport,
) -> MerchantOperationalStatus:
    reasons: list[str] = []

    if report.unmatched > 0:
        reasons.append("unmatched_rows")

    if report.invalid > 0:
        reasons.append("invalid_rows")

    if report.deactivated > 0:
        reasons.append("offers_deactivated")

    if reasons:
        return MerchantOperationalStatus(
            status="review",
            exit_code=10,
            reasons=reasons,
        )

    return MerchantOperationalStatus(
        status="ok",
        exit_code=0,
        reasons=[],
    )


def machine_readable_result(
    report: MerchantImportRunReport,
) -> dict:
    operational = evaluate_import_run(report)

    return {
        "status": operational.status,
        "exit_code": operational.exit_code,
        "reasons": operational.reasons,
        "run": report.model_dump(mode="json"),
    }
