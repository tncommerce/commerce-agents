import pytest
from scripts.dufynd_independent_checker import (
    CHECKS,
    CheckerIdentity,
    make_handoff,
    next_safe_task,
    run_checker,
    verify_receipt,
)


def handoff(**kwargs):
    return make_handoff(
        {"task_id": "a", "instruction": "Audit evidence", **kwargs},
        "Evidence-grounded draft",
        {"repository_evidence": []},
        maker="maker",
    )


def receipt(packet, outcome="accepted"):
    return {
        "handoff_sha256": packet["handoff_sha256"],
        "outcome": outcome,
        "checks": dict.fromkeys(CHECKS, True),
        "additional_evidence": [],
    }


def test_maker_can_never_approve_own_result():
    packet = handoff()
    with pytest.raises(ValueError, match="independent"):
        verify_receipt(packet, receipt(packet), identity=CheckerIdentity("maker"))


@pytest.mark.parametrize(
    "outcome",
    [
        "verified",
        "accepted",
        "needs_more_evidence",
        "rework_required",
        "waiting_external",
        "waiting_human_input",
        "blocked",
    ],
)
def test_checker_outcomes_without_provider(outcome):
    packet = handoff()

    class OfflineChecker:
        def review(self, value):
            assert value is packet
            return receipt(packet, outcome)

    result = run_checker(packet, OfflineChecker(), identity=CheckerIdentity("checker"))
    assert result["outcome"] == outcome
    assert result["automatic_paid_retry"] is False
    assert result["owner_publish_allowed"] is False


def test_acceptance_fails_for_missing_checks_or_evidence():
    packet = handoff()
    invalid = receipt(packet)
    invalid["checks"]["fact_fidelity"] = False
    with pytest.raises(ValueError, match="complete_verification"):
        verify_receipt(packet, invalid, identity=CheckerIdentity("checker"))
    invalid = receipt(packet)
    invalid["additional_evidence"] = ["production clickout"]
    with pytest.raises(ValueError, match="complete_verification"):
        verify_receipt(packet, invalid, identity=CheckerIdentity("checker"))


def test_paid_checker_gate_precedes_invocation():
    class Forbidden:
        def review(self, _):
            raise AssertionError("No paid provider may run")

    with pytest.raises(ValueError, match="new_owner_budget"):
        run_checker(handoff(), Forbidden(), identity=CheckerIdentity("checker", paid=True))


def test_human_gate_and_rework_limit():
    packet = handoff(requires_human_approval=True)
    assert (
        verify_receipt(packet, receipt(packet), identity=CheckerIdentity("checker"))["next_state"]
        == "waiting_human_input"
    )
    packet = make_handoff({"task_id": "a"}, "draft", {}, maker="maker", attempt=1)
    assert (
        verify_receipt(
            packet, receipt(packet, "rework_required"), identity=CheckerIdentity("checker")
        )["next_state"]
        == "blocked"
    )


def test_next_safe_task_requires_verified_dependency():
    packet = handoff()
    decision = verify_receipt(packet, receipt(packet), identity=CheckerIdentity("checker"))
    tasks = [
        {"task_id": "a", "status": "blocked"},
        {"task_id": "b", "status": "ready", "dependencies": ["a"]},
        {"task_id": "c", "status": "ready", "priority": 100, "requires_human_approval": True},
    ]
    assert next_safe_task(tasks, "a", decision)["task_id"] == "b"
    assert next_safe_task(tasks, "a", {"next_state": "blocked"}) is None


def test_tampered_handoff_is_rejected():
    packet = handoff()
    result = receipt(packet)
    packet["maker_result"] = "tampered"
    with pytest.raises(ValueError):
        verify_receipt(packet, result, identity=CheckerIdentity("checker"))
