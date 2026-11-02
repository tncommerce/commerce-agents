"""Fail-closed tests for independent Render deployment / GitHub source-delta receipts."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts.audit_dufynd_render_source_delta import audit_release_snapshot, classify

SOURCE = Path("docs/tech/dufynd-render-source-delta-20261102.json")


def actual_evidence() -> dict:
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def checked_at(evidence: dict) -> datetime:
    return datetime.fromisoformat(
        evidence["observed_at_utc"].replace("Z", "+00:00")
    ).astimezone(UTC)


def audit(evidence: dict, *, hours: int = 0) -> dict:
    return audit_release_snapshot(
        evidence, now=checked_at(evidence) + timedelta(hours=hours)
    )


def test_original_api_and_storefront_receipts_are_distinct_and_verifiable() -> None:
    evidence = actual_evidence()
    r = audit(evidence)
    assert r["status"] == "HEAD_AHEAD_OF_DEPLOYED_RELEASE"
    assert r["source_evidence_stale"] is False
    assert r["services"]["api"]["commits_after_live"] == 105
    assert r["services"]["api"]["changed_file_count"] == 92
    assert r["services"]["storefront"]["commits_after_live"] == 45
    assert r["services"]["storefront"]["changed_file_count"] == 50
    assert r["services"]["api"]["live_source_sha"] != r["services"]["storefront"]["live_source_sha"]
    assert r["render_live_deployments_recognized_in_snapshot"] is True
    assert r["runtime_code_equivalence_verified"] is False
    assert r["release_expectation_approval_updated"] is False
    assert r["automatic_render_deploy_permitted"] is False
    assert r["database_change_authorized"] is False
    assert r["scheduler_delivery_repaired"] is False
    assert r["new_cost_usd"] == 0


def test_expired_source_receipt_must_not_stay_current() -> None:
    evidence = actual_evidence()
    assert audit(evidence, hours=5)["status"] == "STALE_READ_ONLY_EVIDENCE"
    assert audit(evidence, hours=5)["source_evidence_stale"] is True
    assert audit(evidence, hours=4)["source_evidence_stale"] is False


def test_only_fixed_classification_not_equivalence() -> None:
    assert classify("docs/tech/old-release.md") == "documentation_or_test"
    assert classify("tests/test_release.py") == "documentation_or_test"
    assert classify(".github/workflows/observer.yml") == "automation_source"
    assert classify("examples/retail/storefront-web/components/Hero.tsx") == (
        "storefront_source_or_build"
    )
    assert classify("examples/retail/data/catalog.json") == "catalog_or_jarvis_data"
    assert classify("scripts/refresh_scentai_jarvis_state.py") == "worker_or_release_script"
    assert classify("packages/api/service.py") == "other_unclassified"


@pytest.mark.parametrize(
    ("modify", "error"),
    [
        (
            lambda p: p["github_compares"]["storefront"].update(
                {"merge_base_commit": {"sha": "0" * 40}}
            ),
            "compare_not_descendant_of_live",
        ),
        (
            lambda p: p["github_compares"]["api"].update(
                {"base": "f" * 40}
            ),
            "compare_base_mismatch",
        ),
        (
            lambda p: p["github_compares"]["api"].update(
                {"head": "f" * 40}
            ),
            "compare_head_mismatch",
        ),
        (
            lambda p: p["github_compares"]["api"].update(
                {"too_large": True}
            ),
            "compare_truncated",
        ),
        (
            lambda p: p["github_compares"]["api"].update(
                {"behind_by": 1}
            ),
            "compare_branch_diverged",
        ),
        (
            lambda p: p["github_compares"]["api"].update(
                {"ahead_by": 300}
            ),
            "compare_commit_span_incomplete",
        ),
        (
            lambda p: p["github_compares"]["api"]["files"].append(
                p["github_compares"]["api"]["files"][0].copy()
            ),
            "unsafe_or_duplicate_compare_file",
        ),
        (
            lambda p: p["github_compares"]["api"]["files"][0].update(
                {"filename": "../../secret"}
            ),
            "unsafe_or_duplicate_compare_file",
        ),
        (
            lambda p: p["github_compares"]["api"]["files"][0].update(
                {"status": "unknown"}
            ),
            "unknown_file_change_status",
        ),
        (
            lambda p: p["github_compares"]["api"]["files"][0].update(
                {"changes": None}
            ),
            "file_delta_size_unverified",
        ),
        (
            lambda p: p["render_deployments"]["api"].update(
                {"live_status": "deactivated"}
            ),
            "render_release_not_live",
        ),
        (
            lambda p: p["render_deployments"]["api"].update(
                {"deployed_source_sha": "f" * 40}
            ),
            "compare_base_mismatch",
        ),
        (
            lambda p: p["render_deployments"]["storefront"].update(
                {"service_id": "srv-unknown"}
            ),
            "render_service_mismatch",
        ),
        (
            lambda p: p["github_compares"].pop("storefront"),
            "service_pair_incomplete",
        ),
        (
            lambda p: p.update(
                {"observed_repository_head": "bad-sha"}
            ),
            "invalid_repo_head",
        ),
    ],
)
def test_mutations_never_create_automatic_release_approval(modify, error: str) -> None:
    evidence = copy.deepcopy(actual_evidence())
    modify(evidence)
    with pytest.raises(ValueError, match=error):
        audit(evidence)


def test_docs_only_changes_still_cannot_authorize_release() -> None:
    evidence = copy.deepcopy(actual_evidence())
    head = evidence["observed_repository_head"]
    for component, compare in evidence["github_compares"].items():
        base = evidence["render_deployments"][component]["deployed_source_sha"]
        compare["base"] = head
        compare["base_commit"] = {"sha": head}
        compare["merge_base_commit"] = {"sha": head}
        evidence["render_deployments"][component]["deployed_source_sha"] = head
        compare["ahead_by"] = 0
        compare["total_commits"] = 0
        compare["status"] = "identical"
        compare["files"] = []
    report = audit(evidence)
    assert report["status"] == "HEAD_MATCHES_DEPLOYED_RELEASES"
    assert report["runtime_code_equivalence_verified"] is False
    assert report["automatic_render_deploy_permitted"] is False


def test_suspicious_file_and_incomplete_pagination_fail_closed() -> None:
    evidence = copy.deepcopy(actual_evidence())
    evidence["github_compares"]["storefront"]["files"] = (
        evidence["github_compares"]["storefront"]["files"] * 6
    )
    with pytest.raises(ValueError, match="compare_file_list_unavailable_or_truncated"):
        audit(evidence)
