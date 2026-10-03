"""Finalize one provenance-bound DUFYND Private Observer acceptance run.

Consumes only the bounded acknowledgement receipt emitted after idempotent OIDC
ack. This trusted control-plane process may use the existing Supabase service-role
credential but never receives provider credentials or the broker owner key.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from private_broker.observer_contract import ProvenanceError, validate_source
from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge

MAX_RECEIPT_BYTES = 32_768
SUMMARY_KEYS = frozenset(
    {"acknowledged", "duplicate_first_pass", "idempotent_rechecks"}
)


class FinalizeError(RuntimeError):
    pass


def load_receipt(
    path: Path,
    *,
    expected_run_id: str,
    expected_sha: str,
) -> tuple[dict[str, Any], dict[str, int]]:
    try:
        if path.stat().st_size > MAX_RECEIPT_BYTES:
            raise FinalizeError("ack receipt exceeds size limit")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FinalizeError:
        raise
    except Exception:
        raise FinalizeError("ack receipt is unreadable") from None

    if not isinstance(payload, dict) or set(payload) != {"version", "source", "ack_summary"}:
        raise FinalizeError("ack receipt shape mismatch")
    if payload.get("version") != 1:
        raise FinalizeError("ack receipt version mismatch")
    try:
        source = validate_source(
            payload["source"],
            expected_run_id=expected_run_id,
            expected_sha=expected_sha,
        )
    except ProvenanceError as exc:
        raise FinalizeError(f"ack receipt provenance {exc}") from None

    summary = payload.get("ack_summary")
    if not isinstance(summary, dict) or set(summary) != SUMMARY_KEYS:
        raise FinalizeError("ack summary shape mismatch")
    if any(type(summary[key]) is not int or summary[key] < 0 for key in SUMMARY_KEYS):
        raise FinalizeError("ack summary value mismatch")
    if (
        summary["acknowledged"] + summary["duplicate_first_pass"] != 3
        or summary["idempotent_rechecks"] != 3
    ):
        raise FinalizeError("ack summary incomplete")
    return source, summary


def finalize(
    bridge: DufyndJarvisBridge,
    receipt_path: Path,
    *,
    expected_run_id: str,
    expected_sha: str,
) -> dict[str, Any]:
    source, summary = load_receipt(
        receipt_path,
        expected_run_id=expected_run_id,
        expected_sha=expected_sha,
    )
    result = bridge.finalize_broker_acceptance(source=source, ack_summary=summary)
    if (
        result.get("accepted") is not True
        or result.get("activated") != 2
        or result.get("run_id") != int(expected_run_id)
    ):
        raise FinalizeError("broker activation receipt mismatch")
    reconciliation = bridge.reconcile_control_plane()
    return {
        "accepted": True,
        "activated": 2,
        "activation_changed": bool(result.get("activation_changed")),
        "run_id": int(expected_run_id),
        "reconciled": isinstance(reconciliation, dict),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Finalize one DUFYND Private Observer acceptance receipt."
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path("broker-ack-receipt.json"),
    )
    parser.add_argument("--expected-run-id", default=os.getenv("GITHUB_RUN_ID"))
    parser.add_argument("--expected-sha", default=os.getenv("GITHUB_SHA"))
    args = parser.parse_args()
    if not args.expected_run_id or not args.expected_sha:
        raise SystemExit("private observer finalize failed: expected provenance is required")

    try:
        summary = finalize(
            DufyndJarvisBridge(),
            args.receipt,
            expected_run_id=args.expected_run_id,
            expected_sha=args.expected_sha,
        )
    except FinalizeError as exc:
        raise SystemExit(f"private observer finalize failed: {exc}") from None

    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
