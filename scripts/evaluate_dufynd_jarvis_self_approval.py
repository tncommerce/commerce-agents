from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_POLICY_PATH = Path(
    "examples/retail/data/dufynd_jarvis_self_approval_policy_v2.json"
)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _listed_actions(policy: dict[str, Any], class_name: str) -> Any:
    classes = policy.get("action_classes") or {}
    block = classes.get(class_name) or {}
    return block.get("actions") or []


def _path_blockers(
    action_rule: dict[str, Any],
    context: dict[str, Any],
) -> list[str]:
    rule_context = action_rule.get("context") or {}
    blockers: list[str] = []

    expected_branch = rule_context.get("target_branch")
    actual_branch = context.get("target_branch")
    if expected_branch and actual_branch != expected_branch:
        blockers.append(
            f"target_branch_must_equal:{expected_branch}"
        )

    raw_paths = context.get("changed_paths") or []
    changed_paths = [str(path).replace("\\", "/") for path in raw_paths]
    denied_prefixes = [
        str(prefix) for prefix in (rule_context.get("deny_path_prefixes") or [])
    ]
    denied_files = set(
        str(name) for name in (rule_context.get("deny_files") or [])
    )

    for path in changed_paths:
        if any(path.startswith(prefix) for prefix in denied_prefixes):
            blockers.append(f"protected_path:{path}")
        if Path(path).name in denied_files:
            blockers.append(f"protected_file:{path}")

    return blockers


def evaluate_action(
    policy: dict[str, Any],
    *,
    action: str,
    evidence: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    require_active_policy: bool = True,
) -> dict[str, Any]:
    evidence = evidence or {}
    context = context or {}
    version = policy.get("version")
    activation = policy.get("activation") or {}

    base = {
        "action": action,
        "policy_version": version,
        "policy_status": policy.get("status"),
        "evidence": evidence,
        "context": context,
        "evaluated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }

    if require_active_policy and not bool(activation.get("active")):
        return {
            **base,
            "decision": "owner_required",
            "reason": "self_approval_policy_not_active",
            "missing_evidence": [],
            "blockers": ["owner_activation_required"],
        }

    prohibited = set(_listed_actions(policy, "prohibited_without_verified_evidence"))
    if action in prohibited:
        return {
            **base,
            "decision": "prohibited",
            "reason": "policy_prohibited_action",
            "missing_evidence": [],
            "blockers": ["action_is_prohibited"],
        }

    owner_required = set(_listed_actions(policy, "owner_required"))
    if action in owner_required:
        return {
            **base,
            "decision": "owner_required",
            "reason": "owner_gate",
            "missing_evidence": [],
            "blockers": ["owner_approval_required"],
        }

    auto_internal = set(_listed_actions(policy, "auto_internal"))
    if action in auto_internal:
        return {
            **base,
            "decision": "auto_allowed",
            "reason": "internal_auto_scope",
            "missing_evidence": [],
            "blockers": [],
        }

    gated_actions = _listed_actions(policy, "auto_after_evidence")
    if isinstance(gated_actions, dict) and action in gated_actions:
        action_rule = gated_actions[action] or {}
        required = [str(item) for item in (action_rule.get("require_all") or [])]
        missing = [key for key in required if evidence.get(key) is not True]
        blockers = _path_blockers(action_rule, context)

        if missing or blockers:
            return {
                **base,
                "decision": "blocked_missing_evidence",
                "reason": "evidence_or_context_gate_failed",
                "missing_evidence": missing,
                "blockers": blockers,
            }

        return {
            **base,
            "decision": "auto_allowed",
            "reason": "all_self_approval_gates_passed",
            "missing_evidence": [],
            "blockers": [],
        }

    default_decision = (
        (policy.get("decision_contract") or {}).get("default_for_unknown_action")
        or "owner_required"
    )
    return {
        **base,
        "decision": default_decision,
        "reason": "unknown_action_fails_closed",
        "missing_evidence": [],
        "blockers": ["action_not_explicitly_allowlisted"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preview/evaluate the candidate DUFYND Jarvis self-approval policy."
    )
    parser.add_argument("action")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--evidence-json", default="{}")
    parser.add_argument("--context-json", default="{}")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Evaluate candidate rules without requiring activation. Never activates policy.",
    )
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    policy = load_json(args.policy)
    evidence = json.loads(args.evidence_json)
    context = json.loads(args.context_json)
    if not isinstance(evidence, dict) or not isinstance(context, dict):
        parser.error("evidence-json and context-json must decode to JSON objects")

    report = evaluate_action(
        policy,
        action=args.action,
        evidence=evidence,
        context=context,
        require_active_policy=not args.preview,
    )

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "DUFYND Jarvis self-approval | "
            f"action={report['action']} | decision={report['decision']} | "
            f"reason={report['reason']}"
        )
        for blocker in report["blockers"]:
            print(f"  - {blocker}")
        for missing in report["missing_evidence"]:
            print(f"  - missing:{missing}")

    if report["decision"] == "auto_allowed":
        return 0
    if report["decision"] == "blocked_missing_evidence":
        return 20
    if report["decision"] == "owner_required":
        return 21
    return 22


if __name__ == "__main__":
    raise SystemExit(main())
