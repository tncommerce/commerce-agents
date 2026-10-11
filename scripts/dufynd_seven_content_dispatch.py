"""Fenced Supabase handoff for seven zero-provider-cost editorial specialist workers.

No task creation, model, image, publishing, external search or secrets retrieval.
This module runs only pre-registered exact-version FREE tasks through the existing
DUFYND claim_dufynd_worker_v2 / update_dufynd_worker_v2 control plane.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from typing import Any

from scripts.dufynd_seven_content_workers import (
    DEPENDENCIES,
    HANDLERS,
    ROLE_NAMES,
    ROLE_ORDER,
    SUCCESS_STATES,
    WorkerInputError,
    digest,
)

SOURCE_KEY = "content.seven_worker_editorial_pilot_20261011_v1"
SOURCE_KIND = "seven_content_role_v1"
ROUND_KEY_PREFIX = "content.seven_workers.runtime"
OWNER = "seven_content_editorial_free_v1"
FORBIDDEN = [
    "budget.spend",
    "commerce.activate",
    "gmail.send",
    "main.merge",
    "shell.execute",
    "social.publish",
]


def task_id(round_id: str, role: str) -> str:
    if role not in ROLE_ORDER:
        raise WorkerInputError("unknown_role")
    return f"content7:{round_id}:{role}"


def result_key(round_id: str, role: str) -> str:
    return f"{ROUND_KEY_PREFIX}.{round_id}.{role}"


def guard_context(round_id: str, source: dict[str, Any], existing: dict) -> str:
    if source.get("round_id") != round_id or not isinstance(existing, dict):
        raise WorkerInputError("round_source_identity_mismatch")
    for role in ROLE_ORDER:
        if not isinstance(source.get(role), dict):
            raise WorkerInputError("missing_role_source:" + role)
    return digest({"round": round_id, "pilot": source, "existing": existing})


def task_manifest(round_id: str, source: dict[str, Any], existing: dict) -> list[dict]:
    """Offline task-registration proposal; never inserts into production."""
    source_sha = guard_context(round_id, source, existing)
    return [
        {
            "task_id": task_id(round_id, role),
            "domain": "content",
            "title": f"DUFYND {role}: {ROLE_NAMES[role]}",
            "instruction": "Run a verified, deterministic free editorial handoff; no media or posts",
            "status": "queued",  # NOT READY until a separately approved activation.
            "worker_state": "queued",
            "priority": 82,
            "requires_human_approval": False,
            "approval_action_type": "auto_allowed",
            "dependencies": [task_id(round_id, dep) for dep in DEPENDENCIES[role]],
            "owner": "jarvis",
            "resource_scope": [f"db:dufynd.content7.{round_id}.{role}"],
            "budget_class": "free",
            "provider_cost_unknown": False,
            "durability_policy": "durable",
            "external_review_required": False,
            "needs_freshness_recheck": False,
            "required_capabilities": ["content.read", "supabase.task_state"],
            "forbidden_actions": list(FORBIDDEN),
            "durable_payload": {
                "kind": SOURCE_KIND,
                "version": 1,
                "role": role,
                "round_id": round_id,
                "source_key": SOURCE_KEY,
                "source_sha256": source_sha,
                "provider_execution": False,
            },
        }
        for role in ROLE_ORDER
    ]


class SupabaseSevenWorkerDispatch:
    """Reuse the existing fenced worker RPCs; results live in internal master status."""

    def __init__(self, bridge: Any, *, source: dict, existing: dict):
        self.bridge = bridge
        self.source = source
        self.existing = existing
        self.round_id = str(source.get("round_id") or "")
        self.source_sha = guard_context(self.round_id, source, existing)

    def _read_saved(self, role: str) -> dict | None:
        row = self.bridge.load_master_status_entry(result_key(self.round_id, role))
        value = (row or {}).get("value")
        if value is None:
            return None
        if not isinstance(value, dict) or (
            value.get("round_id") != self.round_id
            or value.get("role") != role
            or value.get("source_sha256") != self.source_sha
            or value.get("packet_sha256") != digest(value.get("packet"))
        ):
            raise WorkerInputError("stale_or_corrupt_saved_worker_packet:" + role)
        return value["packet"]

    def _dependencies(self, role: str) -> dict[str, dict] | None:
        results = {}
        for required in DEPENDENCIES[role]:
            row = self.bridge.load_autonomy_task(task_id(self.round_id, required))
            if not isinstance(row, dict) or row.get("status") != "done":
                return None
            value = self._read_saved(required)
            if not isinstance(value, dict) or value.get("state") not in SUCCESS_STATES:
                return None
            results[required] = value
        return results

    def _verify_task(self, role: str) -> dict:
        row = self.bridge.load_autonomy_task(task_id(self.round_id, role))
        if not isinstance(row, dict):
            raise WorkerInputError("task_not_pre_registered:" + role)
        expected = next(
            item
            for item in task_manifest(self.round_id, self.source, self.existing)
            if item["durable_payload"]["role"] == role
        )
        fixed = (
            "task_id",
            "domain",
            "dependencies",
            "budget_class",
            "provider_cost_unknown",
            "resource_scope",
            "required_capabilities",
            "forbidden_actions",
            "durable_payload",
            "requires_human_approval",
            "approval_action_type",
        )
        if any(row.get(key) != expected[key] for key in fixed):
            raise WorkerInputError("worker_contract_or_fingerprint_mismatch:" + role)
        if row.get("status") not in {"ready", "done"}:
            raise WorkerInputError("worker_not_explicitly_activated:" + role)
        return row

    def run_role(self, role: str) -> dict:
        if role not in ROLE_ORDER:
            raise WorkerInputError("unknown_content_role")
        task = self._verify_task(role)
        prior = self._dependencies(role)
        if prior is None:
            return {"role": role, "state": "WAITING_DEPENDENCIES", "spend_eur": 0}

        if task["status"] == "done":
            saved = self._read_saved(role)
            if not isinstance(saved, dict) or saved.get("state") not in SUCCESS_STATES:
                raise WorkerInputError("done_task_missing_evidence:" + role)
            return {"role": role, "state": "ALREADY_DONE", "spend_eur": 0}

        # Existing DB function enforces readiness, resource conflicts, task
        # dependencies and 180s fenced lease. No free-form task interpreter.
        claimed = self.bridge.claim_worker(task["task_id"], OWNER)
        if not isinstance(claimed, dict):
            return {"role": role, "state": "NOT_CLAIMED", "spend_eur": 0}
        self.bridge.update_worker(
            task["task_id"],
            "working",
            evidence="Seven editorial worker claimed; zero model/provider calls.",
        )
        # A crash after the result is stored can resume without rerunning
        # the producer, but completion still requires a valid fenced lease.
        saved = self._read_saved(role)
        if saved is not None:
            result = saved
        else:
            result = HANDLERS[role](self.source[role], prior, self.existing)
            if result.get("state") in SUCCESS_STATES:
                saved_value = {
                    "round_id": self.round_id,
                    "role": role,
                    "task_id": task["task_id"],
                    "source_sha256": self.source_sha,
                    "packet_sha256": digest(result),
                    "packet": result,
                    "cost_eur": 0,
                    "approved_for_publication": False,
                    "visual_quality_verified": False,
                }
                self.bridge.upsert_master_status(
                    key=result_key(self.round_id, role),
                    category="content",
                    value=saved_value,
                    priority=80,
                    last_verified_at=datetime.now(UTC).isoformat(),
                )
        state = result.get("state")
        evidence = json.dumps(
            {
                "role": role,
                "source_sha256": self.source_sha,
                "packet_sha256": digest(result),
                "state": state,
                "holds": result.get("holds", []),
                "new_spend_eur": 0,
                "publication": False,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        if state not in SUCCESS_STATES:
            self.bridge.update_worker(
                task["task_id"], "blocked", evidence=evidence, reason="verification_pending"
            )
            return {"role": role, "state": "BLOCKED", "spend_eur": 0}
        self.bridge.update_worker(task["task_id"], "verifying", evidence=evidence)
        self.bridge.update_worker(task["task_id"], "done", evidence=evidence)
        return {"role": role, "state": state, "spend_eur": 0}

    def build_editor_review_bundle(self) -> dict:
        """Read-only owner-review handoff. Never confers 9.5 or publish approval."""
        packets = {}
        pending = []
        for role in ROLE_ORDER:
            row = self.bridge.load_autonomy_task(task_id(self.round_id, role))
            if not isinstance(row, dict) or row.get("status") != "done":
                pending.append(role)
                continue
            saved = self._read_saved(role)
            if not isinstance(saved, dict) or saved.get("state") not in SUCCESS_STATES:
                pending.append(role)
                continue
            packets[role] = saved
        if pending:
            return {
                "round_id": self.round_id,
                "state": "WAITING_VERIFIED_WORKER_OUTPUTS",
                "pending_roles": pending,
                "spend_eur": 0,
                "creative_go": False,
                "publish_go": False,
            }
        candidates = packets["W2"]["output"].get("editorial_shortlist", [])
        return {
            "round_id": self.round_id,
            "state": "EDITOR_REVIEW_ONLY",
            "source_sha256": self.source_sha,
            "worker_output_hashes": {
                role: digest(packets[role]) for role in ROLE_ORDER
            },
            "candidates": [
                {
                    "id": item["id"],
                    "title": item["title"],
                    "hook": item["hook"],
                    "question": item["community_question"],
                    "format": item["format"],
                    "holds": list(item["review_holds"]) + [
                        "no_visual_or_mobile_9_5_qa",
                        "owner_creative_decision_pending",
                        "separate_publication_audio_ai_rights_go_pending",
                    ],
                }
                for item in candidates[:3]
            ],
            "source_verification_holds": list(packets["W3"]["holds"])
            + list(packets["W4"]["holds"]),
            "visual_score": None,
            "creative_go": False,
            "publish_go": False,
            "spend_eur": 0,
        }

    def run_all(self) -> list[dict]:
        results = []
        for role in ROLE_ORDER:
            result = self.run_role(role)
            results.append(result)
            if result["state"] not in SUCCESS_STATES | {"ALREADY_DONE"}:
                break  # Dependency not complete; no fake autonomous result.
        return results


def load_private_inputs(bridge: Any) -> tuple[dict, dict]:
    row = bridge.load_master_status_entry(SOURCE_KEY)
    value = (row or {}).get("value")
    if not isinstance(value, dict):
        raise WorkerInputError("registered_private_pilot_missing")
    # Bound the round to the actual live Owner freezes and published idea list.
    # An unavailable internal source is a HOLD, never a silent empty snapshot.
    final_keys = (
        "content.my_type_of_alcohol_houseparty_v2_frozen_20261010",
        "content.mirror_dog_she_said_smell_good_v2_frozen_20261010",
        "content.just_two_sprays_elevator_v4_frozen_20261010",
        "content.ghost_perfume_halloween_older_woman_v2_frozen_20261010",
        "content.cafe_47_slides_v3_frozen_20261010",
        "content.friday_cat_notarzt_20261016",
        "content.thursday_goalkeeper_perfume_20261015",
    )
    frozen = []
    for key in final_keys:
        record = bridge.load_master_status_entry(key)
        data = (record or {}).get("value")
        if not isinstance(data, dict):
            raise WorkerInputError("missing_current_owner_freeze_snapshot:" + key)
        freeze = data.get("owner_freeze")
        for candidate in (
            data.get("title"),
            data.get("creative_id"),
            (freeze or {}).get("content_id") if isinstance(freeze, dict) else None,
        ):
            if isinstance(candidate, str) and candidate.strip():
                frozen.append(candidate.strip())
    approval = bridge.load_master_status_entry(
        "content.owner_publish_go_goalkeeper_monday_20261011"
    )
    release = (approval or {}).get("value")
    dates = (release or {}).get("owner_requested_dates")
    if not isinstance(dates, dict) or dates.get("instagram", {}).get("date") != "2026-10-12":
        raise WorkerInputError("monday_torwart_reservation_not_live_verified")
    from scripts.dufynd_jarvis_bridge import _headers

    with bridge._client() as client:
        response = client.get(
            f"{bridge.supabase_url}/rest/v1/dufynd_content_ideas",
            headers=_headers(bridge.secret_key),
            params={"select": "title,status", "order": "title.asc", "limit": "200"},
        )
        response.raise_for_status()
        ideas = response.json()
    if not isinstance(ideas, list):
        raise WorkerInputError("content_ideas_snapshot_invalid")
    published = []
    for item in ideas:
        if not isinstance(item, dict):
            raise WorkerInputError("content_idea_snapshot_row_invalid")
        title = item.get("title")
        status = str(item.get("status") or "").lower()
        if not isinstance(title, str) or not title.strip():
            continue
        if status == "published":
            published.append(title.strip())
        if "frozen" in status or status.startswith("owner_creative_"):
            frozen.append(title.strip())
    existing = {
        "reserved": {"2026-10-12": "Torwart"},
        "published_titles": sorted(set(published)),
        "frozen_titles": sorted(set(frozen)),
        "snapshot_verified": True,
    }
    return value, existing


def main() -> int:
    parser = argparse.ArgumentParser(description="Seven roles on existing DUFYND worker leases")
    parser.add_argument("--output-manifest", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--review-bundle", action="store_true")
    parser.add_argument("--role", choices=ROLE_ORDER)
    args = parser.parse_args()
    if not (args.output_manifest or args.execute or args.review_bundle):
        parser.error("choose --output-manifest or --execute")
    if sum((args.output_manifest, args.execute, args.review_bundle)) > 1:
        parser.error("cannot generate manifest and claim task in one run")
    if args.execute and os.getenv("DUFYND_SEVEN_WORKER_ACTIVATION_GO") != "1":
        raise WorkerInputError("live_worker_activation_requires_separate_owner_gate")

    from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge

    bridge = DufyndJarvisBridge()
    source, existing = load_private_inputs(bridge)
    if args.output_manifest:
        print(json.dumps(task_manifest(source["round_id"], source, existing), ensure_ascii=False))
        return 0
    dispatcher = SupabaseSevenWorkerDispatch(bridge, source=source, existing=existing)
    if args.review_bundle:
        result = dispatcher.build_editor_review_bundle()
    else:
        result = dispatcher.run_role(args.role) if args.role else dispatcher.run_all()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
