"""Seven role dispatcher contracts against the EXISTING fenced Jarvis control plane.

Only synthetic sources and a FakeBridge. Never create production tasks, invoke
an actual provider, touch private creative files or post externally.
"""

from __future__ import annotations

import copy
import unittest
from datetime import UTC, date, datetime, timedelta
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


def editorial_fixture() -> dict:
    """Self-contained synthetic input: no owner data or cross-test imports."""
    hooks = [f"Konkrete Parfum-Situation {i}: der unerwartete Moment" for i in range(20)]
    questions = [f"An welchen ähnlichen Moment Nummer {i} erinnerst du dich?" for i in range(10)]
    first_day = date(2026, 10, 12)
    return {
        "W1": {
            "audience": "newcomers and interested fragrance enthusiasts",
            "voice": "warm, precise and amusing",
            "channels": "TikTok photography, Instagram feed and genuine Shorts",
            "goals": ["shares", "comments", "site visits"],
            "cadence_test_mix": {"meme": 12, "carousel": 9, "reel": 6, "slideshow": 3},
        },
        "W3": {
            "patterns": [
                {
                    "url": "https://example.org/discussion/test-mechanic",
                    "date": "2026-10-08",
                    "mechanic": "Real-life comedy with a specific decision question",
                }
            ]
        },
        "W4": {
            "insights": [
                {
                    "id": f"offline_{i}",
                    "theme": f"Educational note theme {i}",
                    "claim": f"Potential fact requires verifying actual source {i}",
                    "source_url": f"https://example.org/education/insight-{i}",
                }
                for i in range(5)
            ]
        },
        "W5": {"questions": questions},
        "W6": {"hooks": hooks},
        "W2": {
            "ideas": [
                {
                    "id": f"idea_{i}",
                    "title": "Already published scent" if i == 2 else f"New scenario {i}",
                    "hook": hooks[i],
                    "question": questions[i],
                    "format": "meme",
                    "concept": f"A fresh candid scene with a concrete emotional turn {i}",
                    "overlap": "distinct",
                }
                for i in range(10)
            ]
        },
        "W7": {
            "calendar": [
                {
                    "date": (first_day + timedelta(days=i)).isoformat(),
                    "idea": "Torwart owner-frozen original" if i == 0 else f"New topic {i}",
                    "hook": f"Approved source hook or new editorial brief {i}",
                    "format": "meme",
                    "gate": "IDEA_ONLY",
                }
                for i in range(30)
            ]
        },
    }


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
        task["lease_token"] = token
        task["lease_expires_at"] = (datetime.now(UTC) + timedelta(minutes=3)).isoformat()
        task["released_at"] = None
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
        if state == "heartbeat":
            task["lease_expires_at"] = (datetime.now(UTC) + timedelta(minutes=3)).isoformat()
            self.writes.append(("worker", task_id_value, state, evidence))
            return
        task["worker_state"] = state
        if state in {"done", "blocked"}:
            task["status"] = state
        self.writes.append(("worker", task_id_value, state, evidence))

    def _rpc(self, name, payload):
        # Adapter-contract simulation only. Real transaction proof is in SQL tests.
        assert name == "commit_dufynd_content7_result_v1"
        task = self.tasks[payload["p_task_id"]]
        assert task["lease_token"] == payload["p_token"]
        value = payload["p_value"]
        key = result_key(value["round_id"], value["role"])
        assert value["approved_for_publication"] is False
        assert value["visual_quality_verified"] is False
        self.master[key] = {"value": copy.deepcopy(value)}
        self.writes.append(("result", key, value["packet_sha256"]))
        self.update_worker(payload["p_task_id"], "verifying")
        self.update_worker(payload["p_task_id"], "done")
        return True


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
        self.assertTrue(
            all(task["durable_payload"]["provider_execution"] is False for task in manifest)
        )
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

    def test_lost_fence_prevents_untrusted_result_write(self):
        bridge, dispatch = self.make_dispatch()
        original = bridge.load_autonomy_task

        def changed_lease(task_id_value):
            row = original(task_id_value)
            if row is not None and row.get("status") == "in_progress":
                row["lease_token"] = str(uuid4())
            return row

        bridge.load_autonomy_task = changed_lease
        with self.assertRaisesRegex(WorkerInputError, "lease_lost"):
            dispatch.run_role("W1")
        self.assertNotIn(result_key(dispatch.round_id, "W1"), bridge.master)
        self.assertFalse(any(w[0] == "result" for w in bridge.writes))

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
        dispatch = SupabaseSevenWorkerDispatch(bridge, source=changed, existing=self.existing)
        with self.assertRaisesRegex(WorkerInputError, "fingerprint_mismatch"):
            dispatch.run_role("W1")
        self.assertEqual(bridge.claims, [])

    def test_blocked_role_stops_dependent_dispatch_and_claims(self):
        source = copy.deepcopy(self.source)
        source["W5"]["questions"] = source["W5"]["questions"][:9]
        bridge = FakeBridge(source, self.existing)
        dispatch = SupabaseSevenWorkerDispatch(bridge, source=source, existing=self.existing)
        result = dispatch.run_all()
        self.assertEqual([r["role"] for r in result], list(ROLE_ORDER))
        self.assertEqual(result[3]["state"], "BLOCKED")
        self.assertTrue(all(r["state"] == "WAITING_DEPENDENCIES" for r in result[4:]))
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
        self.assertNotEqual(bridge.tasks[task_id(dispatch.round_id, "W1")]["status"], "done")

    def test_chief_editor_receives_only_three_candidates_without_go(self):
        bridge, dispatch = self.make_dispatch()
        before = dispatch.build_editor_review_bundle()
        self.assertEqual(before["state"], "WAITING_VERIFIED_WORKER_OUTPUTS")
        self.assertEqual(set(before["pending_roles"]), set(ROLE_ORDER))
        self.assertFalse(before["publish_go"])
        dispatch.run_all()
        after = dispatch.build_editor_review_bundle()
        self.assertEqual(after["state"], "EDITOR_REVIEW_ONLY")
        self.assertEqual(len(after["candidates"]), 3)
        self.assertFalse(after["publish_go"])
        self.assertFalse(after["creative_go"])
        self.assertIsNone(after["visual_score"])
        self.assertTrue(
            all("no_visual_or_mobile_9_5_qa" in item["holds"] for item in after["candidates"])
        )
        self.assertEqual(len(after["worker_output_hashes"]), 7)
        self.assertTrue(after["source_verification_holds"])
        self.assertEqual(after["spend_eur"], 0)
        # Chief-editor review is read-only; its result is not a fabricated
        # eighth Jarvis worker or an owner decision.
        self.assertEqual(len(bridge.claims), 7)

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
