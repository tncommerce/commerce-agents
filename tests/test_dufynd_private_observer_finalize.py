from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from scripts.dufynd_private_observer_finalize import (
    FinalizeError,
    finalize,
    load_receipt,
)


def source() -> dict[str, Any]:
    return {
        "version": 1,
        "repository": "tncommerce/commerce-agents",
        "repository_id": "1367576041",
        "repository_owner_id": "324597697",
        "ref": "refs/heads/scentai-mvp",
        "workflow_ref": (
            "tncommerce/commerce-agents/.github/workflows/"
            "dufynd-private-observer.yml@refs/heads/scentai-mvp"
        ),
        "event_name": "workflow_dispatch",
        "sha": "a" * 40,
        "run_id": "123456789",
        "run_attempt": "1",
    }


def receipt() -> dict[str, Any]:
    return {
        "version": 1,
        "source": source(),
        "ack_summary": {
            "acknowledged": 3,
            "duplicate_first_pass": 0,
            "idempotent_rechecks": 3,
        },
    }


class FakeBridge:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, Any], dict[str, Any]]] = []
        self.reconciled = 0

    def finalize_broker_acceptance(
        self,
        *,
        source: dict[str, Any],
        ack_summary: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append((source, ack_summary))
        return {
            "accepted": True,
            "activated": 2,
            "activation_changed": True,
            "run_id": 123456789,
        }

    def reconcile_control_plane(self) -> dict[str, Any]:
        self.reconciled += 1
        return {"ok": True}


def write_receipt(path: Path, payload: dict[str, Any] | None = None) -> None:
    path.write_text(json.dumps(payload or receipt()), encoding="utf-8")


def test_finalize_accepts_exact_receipt_then_reconciles(tmp_path: Path) -> None:
    path = tmp_path / "receipt.json"
    write_receipt(path)
    bridge = FakeBridge()

    result = finalize(
        bridge,  # type: ignore[arg-type]
        path,
        expected_run_id="123456789",
        expected_sha="a" * 40,
    )

    assert result == {
        "accepted": True,
        "activated": 2,
        "activation_changed": True,
        "run_id": 123456789,
        "reconciled": True,
    }
    assert len(bridge.calls) == 1
    assert bridge.reconciled == 1


def test_load_receipt_rejects_wrong_run_before_bridge(tmp_path: Path) -> None:
    path = tmp_path / "receipt.json"
    write_receipt(path)

    with pytest.raises(FinalizeError, match="source_run_mismatch"):
        load_receipt(
            path,
            expected_run_id="987654321",
            expected_sha="a" * 40,
        )


@pytest.mark.parametrize(
    "summary",
    [
        {"acknowledged": 2, "duplicate_first_pass": 0, "idempotent_rechecks": 3},
        {"acknowledged": 3, "duplicate_first_pass": 0, "idempotent_rechecks": 2},
        {"acknowledged": -1, "duplicate_first_pass": 4, "idempotent_rechecks": 3},
    ],
)
def test_load_receipt_rejects_incomplete_ack(summary: dict[str, int], tmp_path: Path) -> None:
    path = tmp_path / "receipt.json"
    payload = receipt()
    payload["ack_summary"] = summary
    write_receipt(path, payload)

    with pytest.raises(FinalizeError, match="ack summary"):
        load_receipt(
            path,
            expected_run_id="123456789",
            expected_sha="a" * 40,
        )
