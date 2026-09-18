from __future__ import annotations

import json
import subprocess

from pydantic import BaseModel

from .merchant_automation import decide_automation


class MerchantOperationalRun(BaseModel):
    action: str
    exit_code: int
    import_exit_code: int
    reasons: list[str]
    run_id: str | None = None
    payload: dict | None = None


def run_import_with_gate(
    command: list[str],
) -> MerchantOperationalRun:
    import_command = list(command)

    if "--machine-readable" not in import_command:
        import_command.append("--machine-readable")

    completed = subprocess.run(
        import_command,
        capture_output=True,
        text=True,
        check=False,
    )

    output = completed.stdout.strip()

    try:
        payload = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return MerchantOperationalRun(
            action="hold",
            exit_code=20,
            import_exit_code=completed.returncode,
            reasons=["invalid_import_output"],
        )

    decision = decide_automation(payload)

    if completed.returncode != decision.exit_code:
        return MerchantOperationalRun(
            action="hold",
            exit_code=20,
            import_exit_code=completed.returncode,
            reasons=["process_exit_mismatch"],
            run_id=decision.run_id,
            payload=payload,
        )

    return MerchantOperationalRun(
        action=decision.action,
        exit_code=decision.exit_code,
        import_exit_code=completed.returncode,
        reasons=decision.reasons,
        run_id=decision.run_id,
        payload=payload,
    )
