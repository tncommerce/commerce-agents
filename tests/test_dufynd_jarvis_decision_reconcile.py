from __future__ import annotations

from scripts.dufynd_jarvis_decision_reconcile import (
    build_merge_decision_reconciliation,
    reconcile_pending_merge_decisions,
)


def pending_merge_decision() -> dict:
    return {
        "decision_id": "decision_merge_test",
        "action_type": "merge_production_code",
        "status": "pending",
        "decision_token": "GO-MERGE-TEST",
        "context": {
            "pr_number": 42,
            "head_sha": "head-42",
            "base_branch": "scentai-mvp",
        },
    }


def pull_request(*, state: str, merged_at: str | None = None) -> dict:
    return {
        "number": 42,
        "state": state,
        "merged_at": merged_at,
        "closed_at": "2026-09-30T04:00:00Z" if state == "closed" else None,
        "html_url": "https://github.com/tncommerce/commerce-agents/pull/42",
        "merge_commit_sha": "merge-42" if merged_at else None,
        "head": {"sha": "head-42"},
        "base": {"ref": "scentai-mvp"},
    }


def test_reconciliation_completes_already_merged_pr() -> None:
    action = build_merge_decision_reconciliation(
        pending_merge_decision(),
        pull_request(state="closed", merged_at="2026-09-30T04:10:00Z"),
        resolved_at="2026-09-30T05:00:00+00:00",
    )

    assert action is not None
    assert action["resolution"] == "already_merged"
    assert action["decision"]["merge_commit_sha"] == "merge-42"
    assert "approved" not in action["decision"]


def test_reconciliation_supersedes_closed_unmerged_pr() -> None:
    action = build_merge_decision_reconciliation(
        pending_merge_decision(),
        pull_request(state="closed"),
        resolved_at="2026-09-30T05:00:00+00:00",
    )

    assert action is not None
    assert action["resolution"] == "superseded"
    assert action["decision"]["merged_at"] is None
    assert "approved" not in action["decision"]


def test_reconciliation_leaves_open_pr_pending() -> None:
    action = build_merge_decision_reconciliation(
        pending_merge_decision(),
        pull_request(state="open"),
        resolved_at="2026-09-30T05:00:00+00:00",
    )

    assert action is None


def test_reconciliation_refuses_pr_identity_mismatch() -> None:
    pr = pull_request(state="closed")
    pr["head"]["sha"] = "different-head"

    action = build_merge_decision_reconciliation(
        pending_merge_decision(),
        pr,
        resolved_at="2026-09-30T05:00:00+00:00",
    )

    assert action is None


class FakeBridge:
    def __init__(self) -> None:
        self.completed = []

    def load_pending_decisions(self):
        return [
            pending_merge_decision(),
            {
                "decision_id": "decision_paid",
                "action_type": "buy_subscription_or_credits",
                "status": "pending",
                "context": {},
            },
        ]

    def complete_pending_human_decision_reconciliation(
        self,
        *,
        decision_id,
        decision,
        resolved_at,
    ):
        self.completed.append(
            {
                "decision_id": decision_id,
                "decision": decision,
                "resolved_at": resolved_at,
            }
        )
        return {
            "decision_id": decision_id,
            "status": "completed",
            "decision": decision,
        }


def test_reconcile_pending_merge_decisions_is_dry_run_by_default() -> None:
    bridge = FakeBridge()

    report = reconcile_pending_merge_decisions(
        bridge,
        repository="tncommerce/commerce-agents",
        write=False,
        fetch_pr=lambda _repository, _number: pull_request(state="closed"),
        resolved_at="2026-09-30T05:00:00+00:00",
    )

    assert report["reconciled"] == 1
    assert report["actions"][0]["resolution"] == "superseded"
    assert report["actions"][0]["write_applied"] is False
    assert report["granted_new_approval"] is False
    assert report["merged_pull_request"] is False
    assert bridge.completed == []


def test_reconcile_pending_merge_decisions_writes_only_terminal_bookkeeping() -> None:
    bridge = FakeBridge()

    report = reconcile_pending_merge_decisions(
        bridge,
        repository="tncommerce/commerce-agents",
        write=True,
        fetch_pr=lambda _repository, _number: pull_request(
            state="closed",
            merged_at="2026-09-30T04:10:00Z",
        ),
        resolved_at="2026-09-30T05:00:00+00:00",
    )

    assert report["reconciled"] == 1
    assert report["actions"][0]["resolution"] == "already_merged"
    assert report["actions"][0]["write_applied"] is True
    assert bridge.completed[0]["decision"]["resolution"] == "already_merged"
    assert "approved" not in bridge.completed[0]["decision"]
