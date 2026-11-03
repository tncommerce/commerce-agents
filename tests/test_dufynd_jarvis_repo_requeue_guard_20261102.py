"""Prevent model-budget and terminal Jarvis task resurrection on source drift."""

from __future__ import annotations

from collections import Counter

import pytest
from scripts.sync_dufynd_repo_state_to_supabase import apply_sync_plan, build_sync_plan

NEW_FINGERPRINT = "a" * 64
OLD_FINGERPRINT = "b" * 64


def repo_state(*, require_owner: bool = False) -> dict:
    return {
        "generated_at": "2026-11-02T20:45:00+00:00",
        "source_fingerprint_sha256": NEW_FINGERPRINT,
        "active_domain": "commerce",
        "domains": {
            "commerce": {
                "execution_state": "work_available",
                "next_action_class": "approval_required" if require_owner else "auto_allowed",
                "next_action": "obtain_licensed_image_sources",
                "user_approval_required_now": require_owner,
                "blockers": ["approved_images_incomplete"],
            },
            "content": {
                "execution_state": "manual_step_pending",
                "next_action_class": "manual_state_reconciliation_required",
                "next_action": "reconcile_live_social_state",
                "user_approval_required_now": False,
                "blockers": [],
            },
        },
    }


def task_state(
    status: str,
    *,
    budget_class: str | None = "free",
    fingerprint: str = OLD_FINGERPRINT,
    requires_human_approval: bool = False,
    blocked_reason: str | None = None,
    worker_state: str | None = None,
) -> dict:
    return {
        "task_id": "repo_current_commerce",
        "status": status,
        "budget_class": budget_class,
        "provider_cost_unknown": False,
        "requires_human_approval": requires_human_approval,
        "blocked_reason": blocked_reason,
        "worker_state": worker_state or status,
        "evidence": "source_fingerprint_sha256=" + fingerprint + "; prior business evidence",
    }


class GuardBridge:
    def __init__(self, existing: dict[str, dict] | None = None) -> None:
        self.existing = existing or {}
        self.lookups = []
        self.master = []
        self.tasks = []
        self.actions = []
        self.throw_on: str | None = None

    def load_autonomy_task(self, task_id: str) -> dict | None:
        self.lookups.append(task_id)
        self.actions.append("read:" + task_id)
        if self.throw_on == task_id:
            raise RuntimeError("source_db_read_failed")
        return self.existing.get(task_id)

    def upsert_master_status(self, **row) -> None:
        self.actions.append("write:master")
        self.master.append(row)

    def upsert_autonomy_task(self, **row) -> None:
        self.actions.append("write:" + row["task_id"])
        self.tasks.append(row)


@pytest.mark.parametrize(
    "status", ["ready", "done", "waiting_external", "blocked", "approval_required"]
)
@pytest.mark.parametrize("same_fingerprint", [True, False])
def test_model_budget_task_never_auto_reopened(status: str, same_fingerprint: bool) -> None:
    existing = task_state(
        status,
        budget_class="model",
        fingerprint=NEW_FINGERPRINT if same_fingerprint else OLD_FINGERPRINT,
    )
    bridge = GuardBridge({"repo_current_commerce": existing})
    effect = apply_sync_plan(bridge, build_sync_plan(repo_state()))

    assert effect == {
        "tasks_written": 0,
        "existing_tasks_protected": 1,
        "missing_tasks_not_created": 1,
    }
    assert bridge.tasks == []
    assert bridge.existing["repo_current_commerce"] is existing
    assert bridge.master[0]["value"]["source_fingerprint_sha256"] == NEW_FINGERPRINT


@pytest.mark.parametrize("budget", [None, "", "unknown", "Model", "paid"])
def test_unknown_or_nonfree_existing_budget_fails_closed(budget: str | None) -> None:
    bridge = GuardBridge({"repo_current_commerce": task_state("ready", budget_class=budget)})
    effect = apply_sync_plan(bridge, build_sync_plan(repo_state()))
    assert effect["existing_tasks_protected"] == 1
    assert not any(x["task_id"] == "repo_current_commerce" for x in bridge.tasks)


@pytest.mark.parametrize(
    "status",
    [
        "done",
        "in_progress",
        "waiting_external",
        "waiting_human_input",
        "blocked",
        "approval_required",
        "cancelled",
        "failed_retryable",
        "failed_terminal",
        "stale",
    ],
)
def test_old_free_terminal_or_waiting_work_remains_unmodified(status: str) -> None:
    bridge = GuardBridge({"repo_current_commerce": task_state(status)})
    effect = apply_sync_plan(bridge, build_sync_plan(repo_state()))
    assert effect["existing_tasks_protected"] == 1
    assert not any(x["task_id"] == "repo_current_commerce" for x in bridge.tasks)


@pytest.mark.parametrize("status", ["claimed", "working", "verifying", "in_progress"])
def test_active_free_worker_is_not_ever_rewritten(status: str) -> None:
    bridge = GuardBridge({"repo_current_commerce": task_state("ready", worker_state=status)})
    result = apply_sync_plan(bridge, build_sync_plan(repo_state()))
    assert result["existing_tasks_protected"] == 1
    assert bridge.existing["repo_current_commerce"]["worker_state"] == status


@pytest.mark.parametrize(
    "reason", ["owner_decision", "spend_approval", "publication_approval", "contract_approval"]
)
def test_typed_owner_gate_cannot_be_cleared_by_repo_sync(reason: str) -> None:
    bridge = GuardBridge(
        {
            "repo_current_commerce": task_state(
                "waiting_human_input", blocked_reason=reason, fingerprint=NEW_FINGERPRINT
            )
        }
    )
    effect = apply_sync_plan(bridge, build_sync_plan(repo_state()))
    assert effect["existing_tasks_protected"] == 1
    assert not any(x["task_id"] == "repo_current_commerce" for x in bridge.tasks)


def test_explicit_human_approval_boolean_cannot_be_dropped() -> None:
    bridge = GuardBridge(
        {
            "repo_current_commerce": task_state(
                "ready", requires_human_approval=True, fingerprint=NEW_FINGERPRINT
            )
        }
    )
    effect = apply_sync_plan(bridge, build_sync_plan(repo_state()))
    assert effect["existing_tasks_protected"] == 1
    assert not any(x["task_id"] == "repo_current_commerce" for x in bridge.tasks)


def test_source_tightening_human_gate_still_blocks_existing_free_ready_task() -> None:
    existing = task_state("ready", fingerprint=OLD_FINGERPRINT)
    bridge = GuardBridge({"repo_current_commerce": existing})
    effect = apply_sync_plan(bridge, build_sync_plan(repo_state(require_owner=True)))
    commerce = next(x for x in bridge.tasks if x["task_id"] == "repo_current_commerce")
    assert effect == {
        "tasks_written": 1,
        "existing_tasks_protected": 0,
        "missing_tasks_not_created": 1,
    }
    assert commerce["status"] == "approval_required"
    assert commerce["requires_human_approval"] is True


def test_unmodified_free_ready_task_can_be_safely_synced() -> None:
    bridge = GuardBridge(
        {"repo_current_commerce": task_state("ready", fingerprint=NEW_FINGERPRINT)}
    )
    result = apply_sync_plan(bridge, build_sync_plan(repo_state()))
    assert result == {
        "tasks_written": 1,
        "existing_tasks_protected": 0,
        "missing_tasks_not_created": 1,
    }
    assert bridge.tasks[0]["status"] == "ready"


def test_preflight_retrieves_all_tasks_before_any_db_write() -> None:
    bridge = GuardBridge()
    bridge.throw_on = "repo_current_content"
    with pytest.raises(RuntimeError, match="source_db_read_failed"):
        apply_sync_plan(bridge, build_sync_plan(repo_state()))
    assert bridge.lookups == ["repo_current_commerce", "repo_current_content"]
    assert bridge.master == []
    assert bridge.tasks == []
    assert not any(action.startswith("write:") for action in bridge.actions)


def test_snapshot_only_never_reads_or_writes_tasks() -> None:
    bridge = GuardBridge()
    bridge.throw_on = "repo_current_commerce"
    report = apply_sync_plan(bridge, build_sync_plan(repo_state()), snapshot_only=True)
    assert report == {
        "tasks_written": 0,
        "existing_tasks_protected": 0,
        "missing_tasks_not_created": 0,
    }
    assert bridge.lookups == []
    assert len(bridge.master) == 1
    assert bridge.tasks == []


def test_no_budget_or_leases_implicitly_granted_by_a_repo_sync() -> None:
    bridge = GuardBridge(
        {
            "repo_current_commerce": task_state("waiting_external", budget_class="model"),
            "repo_current_content": {
                **task_state("done", budget_class="model"),
                "task_id": "repo_current_content",
            },
        }
    )
    changes = apply_sync_plan(bridge, build_sync_plan(repo_state()))
    assert changes == {
        "tasks_written": 0,
        "existing_tasks_protected": 2,
        "missing_tasks_not_created": 0,
    }
    assert bridge.tasks == []
    assert Counter(x.split(":")[0] for x in bridge.actions) == Counter({"read": 2, "write": 1})


def test_new_domains_are_not_inserted_as_unapproved_model_work() -> None:
    bridge = GuardBridge()
    effects = apply_sync_plan(bridge, build_sync_plan(repo_state()))
    assert effects == {
        "tasks_written": 0,
        "existing_tasks_protected": 0,
        "missing_tasks_not_created": 2,
    }
    assert bridge.tasks == []
    assert len(bridge.master) == 1


@pytest.mark.parametrize("provider_cost_unknown", [True, "true"])
def test_free_budget_with_unverified_provider_cost_never_requeues(
    provider_cost_unknown: object,
) -> None:
    existing = task_state("ready", fingerprint=NEW_FINGERPRINT)
    existing["provider_cost_unknown"] = provider_cost_unknown
    bridge = GuardBridge({"repo_current_commerce": existing})
    effects = apply_sync_plan(bridge, build_sync_plan(repo_state()))
    assert effects == {
        "tasks_written": 0,
        "existing_tasks_protected": 1,
        "missing_tasks_not_created": 1,
    }
    assert bridge.tasks == []


@pytest.mark.parametrize(
    "worker_state", ["done", "waiting_external", "blocked", "approval_required"]
)
def test_contradictory_ready_task_with_terminal_worker_state_stays_held(
    worker_state: str,
) -> None:
    existing = task_state("ready", fingerprint=NEW_FINGERPRINT, worker_state=worker_state)
    bridge = GuardBridge({"repo_current_commerce": existing})
    effects = apply_sync_plan(bridge, build_sync_plan(repo_state()))
    assert effects == {
        "tasks_written": 0,
        "existing_tasks_protected": 1,
        "missing_tasks_not_created": 1,
    }
    assert bridge.tasks == []


def test_existing_task_identity_mismatch_aborts_before_writing_snapshot() -> None:
    existing = task_state("ready", fingerprint=NEW_FINGERPRINT)
    existing["task_id"] = "repo_current_content"
    bridge = GuardBridge({"repo_current_commerce": existing})
    with pytest.raises(ValueError, match="existing_repo_task_identity_mismatch"):
        apply_sync_plan(bridge, build_sync_plan(repo_state()))
    assert bridge.master == []
    assert bridge.tasks == []
