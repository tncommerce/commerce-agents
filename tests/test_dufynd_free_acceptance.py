import copy
import hashlib
import json
from pathlib import Path

import pytest
from scripts.dufynd_free_acceptance import (
    FixtureChecker,
    coverage,
    failure_fixture,
    maker_fixture,
    simulate,
)
from scripts.dufynd_independent_checker import (
    CheckerIdentity,
    make_handoff,
    next_safe_task,
    run_checker,
)
from scripts.dufynd_worker_evidence import (
    MAX_PROMPT_BYTES,
    ROOT,
    encode,
    pack_evidence,
    projection_rows,
    source_text,
)

pytestmark = pytest.mark.usefixtures("counted_contract_clock")

TASKS = json.loads(
    (Path(__file__).parent / "fixtures/dufynd_pre_canary_real_tasks.json").read_text()
)


@pytest.mark.parametrize("task", TASKS)
def test_exact_task_coverage_provenance_and_complete_fixture_lifecycle(task):
    packet = pack_evidence(task, head="a" * 40)
    assert all(coverage(packet).values())
    assert len(encode(packet)) <= MAX_PROMPT_BYTES == 24576
    for source in packet["repository_evidence"]:
        raw = (ROOT / source["path"]).read_bytes()
        assert source["sha256"] == hashlib.sha256(raw).hexdigest()
        if source.get("missing_anchors") is not None:
            assert not source["missing_anchors"]
            lines = raw.decode().splitlines(keepends=True)
            assert source_text(source) == "".join(
                "".join(lines[a - 1 : b]) for a, b in source["line_ranges"]
            )
    before = copy.deepcopy(TASKS)
    simulation = simulate(task, packet, TASKS)
    assert before == TASKS  # zero live or fixture-input queue mutation
    receipt = simulation["receipt"]
    assert receipt["outcome"] == "verified"
    assert all(receipt["checks"].values())
    assert receipt["task_id"] == task["task_id"]
    assert receipt["packet_sha256"] == packet["packet_sha256"]
    assert (
        receipt["receipt_sha256"]
        == hashlib.sha256(
            encode({k: v for k, v in receipt.items() if k != "receipt_sha256"})
        ).hexdigest()
    )
    assert simulation["terminal"]["checker_invocations"] == 1
    assert simulation["terminal"]["paid_calls"] == 0
    assert simulation["terminal"]["dispatch_allowed"] is False
    if task["domain"] == "research":
        assert simulation["terminal"]["next_safe_task"] == TASKS[1]["task_id"]
    else:
        for source in packet["repository_evidence"]:
            if "data" in source and "pilots" in source["data"]:
                original = json.loads((ROOT / source["path"]).read_text())
                by_id = {p["content_id"]: p for p in original["pilots"]}
                for pilot in projection_rows(source, "pilots"):
                    for key, value in pilot.items():
                        assert value == by_id[pilot["content_id"]][key]


@pytest.mark.parametrize("task", TASKS)
def test_unsupported_claim_is_detected_and_never_unlocks_next_task(task):
    packet = pack_evidence(task, head="a" * 40)
    output = json.loads(maker_fixture(task, packet))
    output["claims"][0]["assertion"] = "Observed live conversion increased 99 percent"
    simulation = simulate(task, packet, TASKS, output=json.dumps(output))
    assert simulation["receipt"]["outcome"] == "rework_required"
    assert not simulation["receipt"]["checks"]["unsupported_claims"]
    assert not simulation["receipt"]["checks"]["hallucinations"]
    assert simulation["terminal"]["next_safe_task"] is None
    assert simulation["terminal"]["automatic_paid_retry"] is False


@pytest.mark.parametrize("task", TASKS)
def test_missing_evidence_yields_needs_more_evidence(task):
    packet = pack_evidence(task, head="a" * 40)
    output = maker_fixture(task, packet)
    packet["repository_evidence"].pop(0)
    packet["packet_sha256"] = hashlib.sha256(
        encode({k: v for k, v in packet.items() if k != "packet_sha256"})
    ).hexdigest()
    result = simulate(task, packet, TASKS, output=output)
    assert result["receipt"]["outcome"] == "needs_more_evidence"
    assert result["terminal"]["state"] == "blocked"
    assert result["terminal"]["next_safe_task"] is None


def test_maker_identity_and_paid_checker_are_rejected_before_invocation():
    task = TASKS[0]
    packet = pack_evidence(task, head="a" * 40)
    handoff = make_handoff(task, maker_fixture(task, packet), packet, maker="maker")
    checker = FixtureChecker()
    with pytest.raises(ValueError, match="independent"):
        run_checker(handoff, checker, identity=CheckerIdentity("maker"))
    with pytest.raises(ValueError, match="new_owner_budget"):
        run_checker(handoff, checker, identity=CheckerIdentity("other", paid=True))
    assert checker.calls == 0


def test_rework_is_bounded_and_receipt_cannot_unlock_other_task_or_gates():
    task = TASKS[0]
    packet = pack_evidence(task, head="a" * 40)
    output = json.loads(maker_fixture(task, packet))
    output["claims"][0]["assertion"] = "unsupported"
    handoff = make_handoff(task, json.dumps(output), packet, maker="maker", attempt=1)
    receipt = run_checker(handoff, FixtureChecker(), identity=CheckerIdentity("checker"))
    assert receipt["next_state"] == "blocked"
    with pytest.raises(ValueError):
        make_handoff(task, "fixture", packet, maker="maker", attempt=2)
    good = simulate(task, packet, TASKS)["receipt"]
    assert next_safe_task(TASKS, TASKS[1]["task_id"], good) is None
    gated = copy.deepcopy(TASKS)
    gated[1]["approval_action_type"] = "publishing"
    assert next_safe_task(gated, task["task_id"], good) is None
    good["task_id"] = "tampered"
    assert next_safe_task(TASKS, task["task_id"], good) is None


@pytest.mark.parametrize("task", TASKS)
def test_real_failure_handler_has_complete_zero_cost_terminal_receipt(task):
    result = failure_fixture(task, head="a" * 40)
    receipt = result["receipt"]
    assert result["actual_provider_calls"] == 0
    assert result["result_code"] == 1
    assert result["task_updates"] == 1
    assert receipt["task_id"] == task["task_id"]
    assert receipt["failure_stage"] == "prepare"
    assert receipt["failure_reason"] == "conservative_input_exceeds_reservation"
    assert receipt["stop_reason"] == "counted_worker_failed_no_retry"
    assert receipt["budget_id"] == "jarvis_nightshift_mini_canary_20261004_002"
    assert receipt["reservation_state"] == "not_created"
    assert receipt["reservation_id"] is None
    assert receipt["provider_dispatched"] is False
    assert receipt["ledger_dispatched"] is False
    assert receipt["cost_usd"] == "0"
    assert receipt["retry_allowed"] is False
    assert receipt["terminal_state"] == "blocked"
    assert receipt["packet_sha256"] == pack_evidence(task, head="a" * 40)["packet_sha256"]
    assert (
        receipt["terminal_receipt_sha256"]
        == hashlib.sha256(
            encode({k: v for k, v in receipt.items() if k != "terminal_receipt_sha256"})
        ).hexdigest()
    )
