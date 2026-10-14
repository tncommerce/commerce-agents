"""Two deterministic PRIVATE value receipts, NOT a scheduler or activation RPC.

Reuse PR775's seven pure handlers and atomic private writer. A later separately
reviewed V1 adapter must provide its existing leases, immutable SQL commit,
approval, deadline, attempt and cron-restore gates. This module never enqueues.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.dufynd_content7_activation import write_private_output
from scripts.dufynd_seven_content_workers import (
    DEPENDENCIES,
    HANDLERS,
    ROLE_NAMES,
    ROLE_ORDER,
    SUCCESS_STATES,
    normalized,
)

VERSION = "nightshift-value/2"
SOURCE_KEYS = {
    "measurement": "query:scentai_analytics_events.first_money_v2",
    "editorial": "content.seven_worker_editorial_pilot_20261011_v1",
    "inventory": "content.published_and_frozen_meme_dedup_guard_20261012",
}
V1_COMMIT = "df790a22712ed685593314d6d0feba6b999bc8a9"
WORKER_COMMIT = "289fba7cf059cca3fa54b1417010b8e5888685ee"
EDITORIAL_ARCHIVE_KEY = "private:DUFYND-7-Worker-Pruefnachweise.zip/revised-source.json@ad9b6c198c6c731568f5cfed85970dc256f11249fb47cdf1db6dd64c3e8f36e9"
SAFETY = {
    "cost_eur": 0,
    "provider_calls": 0,
    "publishing_allowed": False,
    "creative_approval": False,
    "production_activation": False,
}


class ValueHold(ValueError):
    """Stable, non-secret reason; never print untrusted upstream errors."""


def sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def instant(value: object) -> datetime:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError
        return result
    except (TypeError, ValueError) as error:
        raise ValueHold("invalid_aware_timestamp") from error


def checked_source(envelope: dict, *, name: str, pin: str, now: datetime) -> dict:
    if not isinstance(envelope, dict) or set(envelope) != {"key", "read_at", "value"}:
        raise ValueHold("source_envelope_invalid")
    allowed = {SOURCE_KEYS[name]}
    if name == "editorial":
        allowed.add(EDITORIAL_ARCHIVE_KEY)
    if envelope["key"] not in allowed or not isinstance(envelope["value"], dict):
        raise ValueHold("source_identity_invalid")
    if not isinstance(pin, str) or not re.fullmatch(r"[a-f0-9]{64}", pin) or sha(envelope) != pin:
        raise ValueHold("source_pin_mismatch")
    if not now - timedelta(hours=6) <= instant(envelope["read_at"]) <= now:
        raise ValueHold("fresh_source_read_required")
    return envelope["value"]


def first_money(value: dict, *, now: datetime) -> dict:
    """Select ONE evidence-appropriate next action; visitor labels are not humans."""
    fields = {
        "window_start",
        "window_end",
        "query_version",
        "complete",
        "events",
        "unique_events",
        "sessions",
        "qa_sessions",
        "bot_sessions",
        "unknown_sessions",
        "visitor_unverified_sessions",
        "social_tagged_sessions",
        "product_views",
        "offer_views",
        "merchant_clickouts",
        "network_report_available",
    }
    if (
        set(value) != fields
        or type(value["query_version"]) is not int
        or value["query_version"] != 1
        or value["complete"] is not True
    ):
        raise ValueHold("incomplete_measurement_contract")
    start, end = instant(value["window_start"]), instant(value["window_end"])
    if not now - timedelta(hours=6) <= end <= now or not timedelta(0) < end - start <= timedelta(
        days=7
    ):
        raise ValueHold("measurement_window_invalid")
    counts = fields - {
        "window_start",
        "window_end",
        "query_version",
        "complete",
        "network_report_available",
    }
    if any(type(value[k]) is not int or not 0 <= value[k] <= 1_000_000 for k in counts):
        raise ValueHold("measurement_counts_invalid")
    if value["events"] != value["unique_events"]:
        raise ValueHold("events_not_deduplicated")
    if (
        sum(
            value[k]
            for k in (
                "qa_sessions",
                "bot_sessions",
                "unknown_sessions",
                "visitor_unverified_sessions",
            )
        )
        != value["sessions"]
    ):
        raise ValueHold("session_partition_invalid")
    if (
        value["sessions"] > value["events"]
        or any(
            value[k] > value["events"]
            for k in ("product_views", "offer_views", "merchant_clickouts")
        )
        or value["social_tagged_sessions"] > value["sessions"]
    ):
        raise ValueHold("measurement_counts_inconsistent")
    if value["network_report_available"] is not False:
        raise ValueHold("original_network_report_requires_separate_verifier")
    if value["sessions"] - value["qa_sessions"] - value["bot_sessions"] == 0:
        action = "OBSERVE_APPROVED_ORGANIC_ENTRY"
        reason = "No sessions outside known QA/bot classes; absence of eligible events does not prove absence of visitors."
    elif value["social_tagged_sessions"] == 0:
        action = "VERIFY_ONE_APPROVED_SOCIAL_ENTRY"
        reason = "No recorded tagged social session; do not infer a broken CTA or real human count."
    elif value["product_views"] == 0:
        action = "REVIEW_EXISTING_PRODUCT_ENTRY"
        reason = "Tagged sessions exist, but no product view is recorded in the bounded window."
    elif value["offer_views"] == 0:
        action = "REVIEW_OFFER_VISIBILITY_OFFLINE"
        reason = (
            "Product views exist without recorded offer views; reproduce before proposing a fix."
        )
    elif value["merchant_clickouts"] == 0:
        action = "REVIEW_CTA_REACHABILITY_OFFLINE"
        reason = "An offer view is recorded but no clickout; this alone is not a conversion defect."
    else:
        action = "RECONCILE_ORIGINAL_NETWORK_REPORT"
        reason = (
            "Recorded clickouts are not purchases; commissions require original network evidence."
        )
    return {
        "state": "INTERNAL_ACTION_RECEIPT",
        "next_action": action,
        "reason": reason,
        "evidence": value,
        "verified_external_visitors": "UNKNOWN",
        "unmarked_qa_or_bots_excluded": False,
        "revenue": "UNKNOWN",
        "commission": "UNKNOWN",
        "execution": "REVIEW_ONLY_NO_POST_NO_PROFILE_EDIT_NO_CLICKOUT",
        "success_measure": "New deduplicated tagged social sessions; inspect QA/bot provenance before interpreting.",
        **SAFETY,
    }


def editorial_handoff(source: dict, inventory: dict) -> dict:
    """Execute existing pure roles; preserve HOLDs and use copy only as internal input."""
    if any(not isinstance(source.get(role), dict) for role in ROLE_ORDER):
        raise ValueHold("seven_role_sources_required")
    if inventory.get("status") != "ACTIVE_DEDUP_GUARD_PUBLISHED_AND_FROZEN" or any(
        not isinstance(inventory.get(k), list) or not inventory[k]
        for k in ("published", "preapproved_or_queued", "rejected_exclusions")
    ):
        raise ValueHold("current_frozen_and_rejected_inventory_required")
    # Preserve whole semantic exclusion registry for human comparison. Exact
    # string matches add protection but are never represented as semantic QA.
    titles = [
        str(row.get("theme") or row.get("mechanic") or row.get("title") or "")
        for key in ("published", "preapproved_or_queued", "rejected_exclusions")
        for row in inventory[key]
        if isinstance(row, dict)
    ]
    existing = {"frozen_titles": titles, "published_titles": titles, "reserved": {}}
    packets = {}
    for role in ROLE_ORDER:
        missing = [d for d in DEPENDENCIES[role] if packets[d]["state"] not in SUCCESS_STATES]
        if missing:
            packets[role] = {
                "state": "BLOCKED",
                "output": {},
                "holds": ["unmet_dependencies:" + ",".join(missing)],
                "cost_eur": 0,
            }
            continue
        packets[role] = HANDLERS[role](
            source[role], {d: packets[d] for d in DEPENDENCIES[role]}, existing
        )
        if type(packets[role].get("cost_eur")) is not int or packets[role]["cost_eur"] != 0:
            raise ValueHold("worker_cost_contract_changed")
    exclusions = {normalized(t) for t in titles}
    candidates = [
        p
        for p in packets["W2"]["output"].get("editorial_shortlist", [])
        if normalized(p["title"]) not in exclusions and not p["review_holds"]
    ][:1]
    # Never schedule W7 dates from an old packet; request a fresh editorial slot.
    role_handoffs = [
        {
            "role": r,
            "name": ROLE_NAMES[r],
            "state": packets[r]["state"],
            "source_pointer": "/" + r,
            "packet_sha256": sha(packets[r]),
            "holds": packets[r]["holds"],
        }
        for r in ROLE_ORDER
    ]
    broken = set(packets["W2"]["output"].get("broken_crosslink_ids", []))
    repair_handoff = [
        {
            "source_idea_id": idea.get("id"),
            "source_pointer": f"/W2/ideas/{index}",
            "hook_matches_W6": idea.get("hook") in packets["W6"]["output"].get("hooks", []),
            "question_matches_W5": idea.get("question")
            in packets["W5"]["output"].get("questions", []),
            "required_action": "Editor must supply an exact, semantically reviewed W5/W6 linkage in a NEW private source version. Do not rewrite frozen originals or auto-substitute copy.",
        }
        for index, idea in enumerate(source["W2"].get("ideas", [])[:25])
        if isinstance(idea, dict) and idea.get("id") in broken
    ]
    return {
        "state": "INTERNAL_EDITORIAL_HANDOFF" if candidates else "OWNER_HOLD",
        "candidate_for_similarity_review_only": candidates,
        "role_handoffs": role_handoffs,
        "repair_handoff": repair_handoff,
        "source_round": source.get("round_id"),
        "exclusion_registry_sha256": sha(inventory),
        "next_steps": [
            "W2: compare the exact candidate premise with ALL frozen/published/rejected mechanics; choose a different existing input if overlapping.",
            "W3/W4: verify original sources and exact claims; dated links alone do not clear rights or facts.",
            "W7: prepare a fresh unreserved proposal only after Chief Editor review; do not reuse historical calendar dates.",
            "Chief Editor: rights-cleared actual visual, mobile QA and honest >=9.5/10 before Owner creative review.",
        ],
        "holds": [
            "semantic_originality_unverified",
            "rights_and_source_clearance_required",
            "actual_visual_qa_9_5_required",
            "owner_creative_review_required",
            "separate_publication_go_required",
        ],
        "visual_score": None,
        "required_visual_score": 9.5,
        "ready_for_owner_visual_review": False,
        "scheduled": False,
        "autonomous_creative_generation": False,
        "worker_source_commit": WORKER_COMMIT,
        **SAFETY,
    }


def prepare(sources: dict, pins: dict, *, now: datetime) -> dict:
    """Two independent inert proposals; one HOLD never blocks the other handler."""
    if (
        now.tzinfo is None
        or set(sources) != set(SOURCE_KEYS)
        or set(pins) != set(SOURCE_KEYS)
        or any(
            not isinstance(pin, str) or not re.fullmatch(r"[a-f0-9]{64}", pin)
            for pin in pins.values()
        )
    ):
        raise ValueHold("bounded_inputs_required")
    results = []
    for handler, names in (
        ("first_money_action/2", ("measurement",)),
        ("editorial_handoff/2", ("editorial", "inventory")),
    ):
        try:
            values = [checked_source(sources[n], name=n, pin=pins[n], now=now) for n in names]
            result = (
                first_money(values[0], now=now) if len(values) == 1 else editorial_handoff(*values)
            )
        except (ValueError, TypeError, KeyError, IndexError) as error:
            reason = str(error) if isinstance(error, ValueHold) else "invalid_source_contract"
            result = {"state": "OWNER_HOLD", "reason": reason, **SAFETY}
        # Reading identical source records on another night is NOT a new task.
        # Acquisition pins bind the fresh read, stable value pins deduplicate work.
        try:
            records = {
                n: {"key": sources[n]["key"], "value_sha256": sha(sources[n]["value"])}
                for n in names
            }
        except (ValueError, TypeError, KeyError):
            records = {n: {"invalid_source_pin": pins[n]} for n in names}
        identity = {"handler": handler, "sources": records, "version": VERSION}
        results.append(
            {
                "task_key_proposal": "nightshift:value:v2:" + sha(identity),
                "handler": handler,
                "input_binding": identity,
                "result": result,
                "result_sha256": sha(result),
                "enqueue_allowed": False,
                "acquisition_pins": {n: pins[n] for n in names},
            }
        )
    return {
        "version": VERSION,
        "state": "PRIVATE_PREPARATION_ONLY",
        "items": results,
        "max_tasks": 2,
        "spend_cap_eur": 0,
        "provider_execution": False,
        "execution_contract": {
            "existing_control_plane": "dufynd_autonomy_tasks + Supervisor V2 leases",
            "v1_reference_commit": V1_COMMIT,
            "lease_seconds": 180,
            "max_attempts_per_task": 3,
            "max_total_attempts": 6,
            "pilot_minutes": 45,
            "statement_timeout_ms": 120000,
            "new_scheduler": False,
            "new_queue": False,
            "runtime_adapter_verified": False,
            "activation_gate": "NATIVE_V1_ACCEPTS_ONLY_ITS_TWO_QA_HANDLERS; REVIEWED_ADAPTER_AND_NEW_EXACT_GO_REQUIRED",
        },
        **SAFETY,
    }


def save_private(path: Path, plan: dict) -> str:
    """Reuse atomic output; same immutable checkpoint cannot be silently replaced."""
    root = Path(__file__).resolve().parents[1]
    target = path.resolve()
    if root == target or root in target.parents or path.is_symlink():
        raise ValueHold("private_output_outside_repository_required")
    if (
        plan.get("version") != VERSION
        or plan.get("max_tasks") != 2
        or plan.get("spend_cap_eur") != 0
        or plan.get("provider_execution") is not False
        or len(plan.get("items", [])) != 2
        or any(plan.get(k) != v or type(plan.get(k)) is not type(v) for k, v in SAFETY.items())
        or any(
            item.get("enqueue_allowed") is not False
            or item.get("result_sha256") != sha(item.get("result"))
            or any(
                item.get("result", {}).get(k) != v
                or type(item.get("result", {}).get(k)) is not type(v)
                for k, v in SAFETY.items()
            )
            for item in plan["items"]
        )
    ):
        raise ValueHold("unsafe_or_corrupt_plan")
    envelope = {"plan": plan, "sha256": sha(plan)}
    lock = path.with_suffix(path.suffix + ".lock")
    if lock.is_symlink():
        raise ValueHold("private_lock_symlink_denied")
    with lock.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        if path.exists():
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise ValueHold("checkpoint_unreadable") from error
            if saved != envelope:
                raise ValueHold("checkpoint_conflict_or_corrupt")
            return "ALREADY_PREPARED"
        write_private_output(path, envelope)
        return "PREPARED"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--expected-pins", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = prepare(
        json.loads(args.input.read_text(encoding="utf-8")),
        json.loads(args.expected_pins.read_text(encoding="utf-8")),
        now=datetime.now(UTC),
    )
    state = save_private(args.output, plan)
    print(
        json.dumps(
            {
                "state": state,
                "sha256": sha(plan),
                "items": [
                    {"handler": item["handler"], "state": item["result"]["state"]}
                    for item in plan["items"]
                ],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
