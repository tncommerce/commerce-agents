"""Seven role dispatcher contracts against the EXISTING fenced Jarvis control plane.

Only synthetic sources and a FakeBridge. Never create production tasks, invoke
an actual provider, touch private creative files or post externally.
"""

from __future__ import annotations

import copy
import unittest
from uuid import uuid4

from scripts.dufynd_jarvis_runtime import _is_green_autonomy_task
from scripts.dufynd_seven_content_dispatch import (
    SOURCE_KEY,
    SOURCE_KIND,
    SupabaseSevenWorkerDispatch,
    result_key,
    task_id,
    task_manifest,
)
from scripts.dufynd_seven_content_workers import ROLE_ORDER, WorkerInputError
from test_dufynd_seven_content_workers import editorial_fixture


class FakeBridge:
    def __init__(self, source: dict, existing: dict, *, activated: bool = True):
        self.source = copy.deepcopy(source)
        self.existing = copy.deepcopy(existing)
        self.round_id = self.source["round_id"]
        self.master = {SOURCE_KEY: {"value": copy.deepcopy(source)}}
        self.tasks = {}
        for task in task_manifest(self.round_id, source, existing):
            task = copy.deepcopy(task)
            if activated:
                task["status"] = "ready"
                task["worker_state"] = "ready"
            self.tasks[task["task_id"]] = task
        self.claims = []
        self.writes = []
        self.worker_tokens = {}

    def load_autonomy_task(self, task_id_value):
        record = self.tasks.get(task_id_value)
        return copy.deepcopy(record) if record else None

    def load_master_status_entry(self, key):
        record = self.master.get(key)
        return copy.deepcopy(record) if record else None

    def claim_worker(self, task_id_value, owner):
        task = self.tasks[task_id_value]
        if task["status"] != "ready":
            return None
        if any(self.tasks[dep]["status"] != "done" for dep in task["dependencies"]):
            return None
        token = str(uuid4())
        self.worker_tokens[task_id_value] = token
        task["status"] = "in_progress"
        task["worker_state"] = "claimed"
        self.claims.append((task_id_value, owner))
        return copy.deepcopy(task)

    def update_worker(self, task_id_value, state, *, evidence=None, reason=None):
        task = self.tasks[task_id_value]
        if task["status"] != "in_progress" or task_id_value not in self.worker_tokens:
            raise RuntimeError("fence_lost")
        if state == "done" and task["worker_state"] != "verifying":
            raise RuntimeError("no_verified_completion")
        task["worker_state"] = state
        if state in {"done", "blocked"}:
            task["status"] = state
        self.writes.append(("worker", task_id_value, state, evidence))

    def upsert_master_status(self, *, key, category, value, priority, last_verified_at):
        assert category == "content" and priority == 80
        assert value["approved_for_publication"] is False
        assert value["visual_quality_verified"] is False
        self.master[key] = {"value": copy.deepcopy(value)}
        self.writes.append(("result", key, value["packet_sha256"]))


class SupabaseContentDispatchTests(unittest.TestCase):
    def setUp(self):
        self.source = editorial_fixture()
        self.source["round_id"] = "dufynd_editorial_seven_worker_dispatch_test_v1"
        self.existing = {
            "reserved": {"2026-10-12": "Torwart"},
            "frozen_titles": ["Frozen approved owner visual"],
            "published_titles": ["Already published scent"],
        }

    def make_dispatch(self, *, activated=True):
        bridge = FakeBridge(self.source, self.existing, activated=activated)
        return bridge, SupabaseSevenWorkerDispatch(
            bridge, source=self.source, existing=self.existing
        )

    def test_task_proposals_are_inert_until_separately_activated(self):
        manifest = task_manifest(self.source["round_id"], self.source, self.existing)
        self.assertEqual(len(manifest), 7)
        self.assertEqual({task["durable_payload"]["role"] for task in manifest}, set(ROLE_ORDER))
        self.assertTrue(all(task["status"] == "queued" for task in manifest))
        self.assertTrue(all(task["budget_class"] == "free" for task in manifest))
        self.assertTrue(all(task["provider_cost_unknown"] is False for task in manifest))
        self.assertTrue(all(task["durable_payload"]["provider_execution"] is False for task in manifest))
        self.assertTrue(all("social.publish" in task["forbidden_actions"] for task in manifest))
        bridge, dispatch = self.make_dispatch(activated=False)
        with self.assertRaisesRegex(WorkerInputError, "not_explicitly_activated"):
            dispatch.run_role("W1")
        self.assertEqual(bridge.claims, [])

    def test_all_seven_real_claims_are_fenced_and_source_bound(self):
        bridge, dispatch = self.make_dispatch()
        results = dispatch.run_all()
        self.assertEqual(len(results), 7)
        self.assertEqual([r["role"] for r in results], list(ROLE_ORDER))
        self.assertTrue(all(r["state"] in {"DONE", "DONE_WITH_HOLDS"} for r in results))
        self.assertEqual(len(bridge.claims), 7)
        self.assertEqual(len([w for w in bridge.writes if w[0] == "result"]), 7)
        self.assertEqual(len([w for w in bridge.writes if w[0] == "worker" and w[2] == "done"]), 7)
        for role in ROLE_ORDER:
            self.assertEqual(bridge.tasks[task_id(dispatch.round_id, role)]["status"], "done")
            saved = bridge.master[result_key(dispatch.round_id, role)]["value"]
            self.assertEqual(saved["source_sha256"], dispatch.source_sha)
            self.assertFalse(saved["approved_for_publication"])
            self.assertFalse(saved["visual_quality_verified"])

    def test_done_is_idempotent_not_a_second_worker_claim(self):
        bridge, dispatch = self.make_dispatch()
        dispatch.run_all()
        before = copy.deepcopy(bridge.writes)
        self.assertEqual(dispatch.run_role("W1")["state"], "ALREADY_DONE")
        self.assertTrue(all(r["state"] == "ALREADY_DONE" for r in dispatch.run_all()))
        self.assertEqual(bridge.writes, before)

    def test_w4_can_finish_before_w3_but_w5_must_wait_for_w3(self):
        bridge, dispatch = self.make_dispatch()
        self.assertEqual(dispatch.run_role("W1")["state"], "DONE")
        self.assertEqual(dispatch.run_role("W4")["state"], "DONE_WITH_HOLDS")
        self.assertEqual(dispatch.run_role("W5")["state"], "WAITING_DEPENDENCIES")
        self.assertEqual(dispatch.run_role("W3")["state"], "DONE_WITH_HOLDS")
        self.assertEqual(dispatch.run_role("W5")["state"], "DONE")

    def test_invalid_contract_is_rejected_before_claim(self):
        bridge, dispatch = self.make_dispatch()
        bridge.tasks[task_id(dispatch.round_id, "W1")]["budget_class"] = "model"
        with self.assertRaisesRegex(WorkerInputError, "worker_contract"):
            dispatch.run_role("W1")
        self.assertEqual(bridge.claims, [])

    def test_source_changed_after_registration_rejects_stale_tasks(self):
        bridge, _dispatch = self.make_dispatch()
        changed = copy.deepcopy(self.source)
        changed["W1"]["voice"] = "unauthorized changed source"
        dispatch = SupabaseSevenWorkerDispatch(
            bridge, source=changed, existing=self.existing
        )
        with self.assertRaisesRegex(WorkerInputError, "fingerprint_mismatch"):
            dispatch.run_role("W1")
        self.assertEqual(bridge.claims, [])

    def test_blocked_role_stops_dependent_dispatch_and_claims(self):
        source = copy.deepcopy(self.source)
        source["W5"]["questions"] = source["W5"]["questions"][:9]
        bridge = FakeBridge(source, self.existing)
        dispatch = SupabaseSevenWorkerDispatch(
            bridge, source=source, existing=self.existing
        )
        result = dispatch.run_all()
        self.assertEqual([r["role"] for r in result], ["W1", "W3", "W4", "W5"])
        self.assertEqual(result[-1]["state"], "BLOCKED")
        self.assertEqual(bridge.tasks[task_id(dispatch.round_id, "W5")]["status"], "blocked")
        self.assertNotIn(result_key(dispatch.round_id, "W5"), bridge.master)
        self.assertEqual(len(bridge.claims), 4)

    def test_stale_saved_result_does_not_overwrite_without_error(self):
        bridge, dispatch = self.make_dispatch()
        key = result_key(dispatch.round_id, "W1")
        bridge.master[key] = {
            "value": {
                "round_id": dispatch.round_id,
                "role": "W1",
                "source_sha256": "invalid-stale",
                "packet_sha256": "invalid",
                "packet": {"state": "DONE", "output": {}},
            }
        }
        with self.assertRaisesRegex(WorkerInputError, "stale_or_corrupt"):
            dispatch.run_role("W1")
        self.assertNotEqual(
            bridge.tasks[task_id(dispatch.round_id, "W1")]["status"], "done"
        )

    def test_generic_model_queue_excludes_specialist_tasks(self):
        manifest = task_manifest(self.source["round_id"], self.source, self.existing)
        specialized = copy.deepcopy(manifest[0])
        specialized["status"] = "ready"
        self.assertEqual(specialized["durable_payload"]["kind"], SOURCE_KIND)
        self.assertFalse(_is_green_autonomy_task(specialized))
        normal = {
            "domain": "content",
            "requires_human_approval": False,
            "approval_action_type": "auto_allowed",
            "durable_payload": {"kind": "content_reuse_shortlist"},
        }
        self.assertTrue(_is_green_autonomy_task(normal))

    def test_nonmatching_role_is_not_generic_fallback(self):
        _bridge, dispatch = self.make_dispatch()
        with self.assertRaisesRegex(WorkerInputError, "unknown_content_role"):
            dispatch.run_role("W8")


if __name__ == "__main__":
    unittest.main()
