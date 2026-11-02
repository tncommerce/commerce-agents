"""Read-only DUFYND GitHub-to-Render release-source boundary audit.

This accepts exact, independently captured GitHub comparison metadata and Render
deployment receipts. It NEVER proves build/runtime equivalence, refreshes a
release approval, starts a deployment or calls an external API.

Run it on a sanitized, immutable evidence JSON snapshot. Incomplete GitHub
comparison metadata fails closed instead of treating missing files as unchanged.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO = "tncommerce/commerce-agents"
BRANCH = "scentai-mvp"
SERVICES = {
    "api": "srv-dakpfrnf3r2c73dr3f20",
    "storefront": "srv-dakpiajl550s73cp4lvg",
}
SHA = re.compile(r"[0-9a-f]{40}\Z")
DEPLOY = re.compile(r"dep-[a-z0-9]+\Z")
SAFE_PATH = re.compile(r"(?!/)(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9_.@/+ -]+\Z")
SUPPORTED_STATUS = {"added", "modified", "removed", "renamed", "copied", "changed"}
DEFAULT_INPUT = Path("docs/tech/dufynd-render-source-delta-20261102.json")


def require(value: bool, reason: str) -> None:
    if not value:
        raise ValueError(reason)


def timestamp(text: str) -> datetime:
    require(isinstance(text, str), "invalid_evidence_timestamp")
    try:
        instant = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_evidence_timestamp") from exc
    require(instant.tzinfo is not None, "unqualified_evidence_timestamp")
    return instant.astimezone(UTC)


def classify(path: str) -> str:
    """A discovery aid; not evidence of binary or behavioral equivalence."""
    if path.startswith(("docs/", "tests/")):
        return "documentation_or_test"
    if path.startswith(".github/workflows/"):
        return "automation_source"
    if path.startswith("examples/retail/storefront-web/"):
        return "storefront_source_or_build"
    if path.startswith("examples/retail/data/"):
        return "catalog_or_jarvis_data"
    if path.startswith("scripts/"):
        return "worker_or_release_script"
    return "other_unclassified"


def validate_comparison(
    payload: dict[str, Any], *, deployed_sha: str, current_sha: str
) -> dict[str, Any]:
    require(isinstance(payload, dict), "comparison_invalid")
    require(payload.get("repository_full_name") == REPO, "compare_repository_mismatch")
    require(payload.get("base") == deployed_sha, "compare_base_mismatch")
    require(payload.get("head") == current_sha, "compare_head_mismatch")
    require(
        (payload.get("base_commit") or {}).get("sha") == deployed_sha,
        "compare_base_receipt_missing",
    )
    require(
        (payload.get("merge_base_commit") or {}).get("sha") == deployed_sha,
        "compare_not_descendant_of_live",
    )
    require(payload.get("too_large") in (None, False), "compare_truncated")
    require(payload.get("behind_by") == 0, "compare_branch_diverged")
    ahead = payload.get("ahead_by")
    commits = payload.get("total_commits")
    require(
        type(ahead) is int
        and type(commits) is int
        and ahead >= 0
        and ahead == commits
        and ahead <= 250,
        "compare_commit_span_incomplete",
    )
    status = payload.get("status")
    require(
        status == ("ahead" if ahead else "identical"),
        "compare_status_inconsistent",
    )
    files = payload.get("files")
    require(
        isinstance(files, list) and len(files) < 300,
        "compare_file_list_unavailable_or_truncated",
    )
    require((len(files) > 0) == (ahead > 0), "compare_files_missing")
    names: set[str] = set()
    groups: dict[str, int] = {}
    for entry in files:
        require(isinstance(entry, dict), "comparison_file_invalid")
        name = entry.get("filename")
        require(
            isinstance(name, str)
            and 1 <= len(name) <= 350
            and bool(SAFE_PATH.fullmatch(name))
            and "\\" not in name
            and name not in names,
            "unsafe_or_duplicate_compare_file",
        )
        names.add(name)
        require(entry.get("status") in SUPPORTED_STATUS, "unknown_file_change_status")
        require(
            type(entry.get("changes")) is int and entry["changes"] >= 0,
            "file_delta_size_unverified",
        )
        if entry["status"] == "renamed":
            previous = entry.get("previous_filename")
            require(
                isinstance(previous, str)
                and bool(SAFE_PATH.fullmatch(previous))
                and previous != name
                and "\\" not in previous,
                "rename_source_unverified",
            )
        group = classify(name)
        groups[group] = groups.get(group, 0) + 1
    return {
        "compared_from": deployed_sha,
        "compared_to": current_sha,
        "commits_after_live": ahead,
        "changed_file_count": len(files),
        "file_groups": dict(sorted(groups.items())),
        # A changed docs/tests-only diff is also NOT a source-equivalence proof.
        "code_equivalence_verified": False,
    }


def audit_release_snapshot(
    evidence: dict[str, Any], *, now: datetime | None = None
) -> dict[str, Any]:
    require(
        isinstance(evidence, dict) and evidence.get("schema_version") == 1,
        "unsupported_release_audit_schema",
    )
    require(
        evidence.get("repository") == REPO and evidence.get("branch") == BRANCH,
        "release_audit_repository_mismatch",
    )
    head = evidence.get("observed_repository_head")
    require(isinstance(head, str) and bool(SHA.fullmatch(head)), "invalid_repo_head")
    stamp = timestamp(evidence.get("observed_at_utc"))
    current = (now or datetime.now(UTC)).astimezone(UTC)
    age = current - stamp
    require(age >= timedelta(minutes=-5), "future_evidence_not_authoritative")
    render = evidence.get("render_deployments")
    compares = evidence.get("github_compares")
    require(
        isinstance(render, dict)
        and isinstance(compares, dict)
        and set(render) == set(compares) == set(SERVICES),
        "service_pair_incomplete",
    )
    details = {}
    for component, expected_id in SERVICES.items():
        deployment = render[component]
        require(isinstance(deployment, dict), "render_receipt_missing")
        require(deployment.get("service_id") == expected_id, "render_service_mismatch")
        require(deployment.get("live_status") == "live", "render_release_not_live")
        require(
            isinstance(deployment.get("deployment_id"), str)
            and bool(DEPLOY.fullmatch(deployment["deployment_id"])),
            "invalid_render_deploy_id",
        )
        sha = deployment.get("deployed_source_sha")
        require(isinstance(sha, str) and bool(SHA.fullmatch(sha)), "invalid_render_sha")
        details[component] = {
            "deployment_id": deployment["deployment_id"],
            "live_source_sha": sha,
            **validate_comparison(compares[component], deployed_sha=sha, current_sha=head),
        }
    stale = age > timedelta(hours=4)
    any_drift = any(x["commits_after_live"] for x in details.values())
    return {
        "status": "STALE_READ_ONLY_EVIDENCE"
        if stale
        else ("HEAD_AHEAD_OF_DEPLOYED_RELEASE" if any_drift else "HEAD_MATCHES_DEPLOYED_RELEASES"),
        "repository": REPO,
        "branch": BRANCH,
        "observed_repository_head": head,
        "observed_at_utc": stamp.isoformat(),
        "source_evidence_stale": stale,
        "services": details,
        "render_live_deployments_recognized_in_snapshot": True,
        "deployment_change_observed_by_this_audit": False,
        "runtime_code_equivalence_verified": False,
        "release_expectation_approval_updated": False,
        "automatic_render_deploy_permitted": False,
        "database_change_authorized": False,
        "scheduler_delivery_repaired": False,
        "new_cost_usd": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    result = audit_release_snapshot(evidence)
    print(
        json.dumps(
            result, ensure_ascii=False, sort_keys=True, indent=None if args.machine_readable else 2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
