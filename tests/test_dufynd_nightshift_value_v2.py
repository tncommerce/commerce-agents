"""Synthetic offline V2 preparation; NOT a pg_cron/native pilot test."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from scripts import dufynd_nightshift_value_v2 as v2
from tests.test_dufynd_seven_content_workers import editorial_fixture

NOW = datetime(2026, 10, 14, 5, tzinfo=UTC)


def inputs():
    measurement = {
        "window_start": "2026-10-13T08:08:00Z",
        "window_end": NOW.isoformat(),
        "query_version": 1,
        "complete": True,
        "events": 31,
        "unique_events": 31,
        "sessions": 22,
        "qa_sessions": 0,
        "bot_sessions": 0,
        "unknown_sessions": 0,
        "visitor_unverified_sessions": 22,
        "social_tagged_sessions": 0,
        "product_views": 7,
        "offer_views": 1,
        "merchant_clickouts": 0,
        "network_report_available": False,
    }
    inventory = {
        "status": "ACTIVE_DEDUP_GUARD_PUBLISHED_AND_FROZEN",
        "published": [{"title": "Already published scent"}],
        "preapproved_or_queued": [{"theme": "Synthetic frozen premise"}],
        "rejected_exclusions": [{"theme": "Synthetic rejected premise"}],
    }
    values = {"measurement": measurement, "editorial": editorial_fixture(), "inventory": inventory}
    sources = {
        name: {"key": v2.SOURCE_KEYS[name], "read_at": NOW.isoformat(), "value": value}
        for name, value in values.items()
    }
    return sources, {name: v2.sha(value) for name, value in sources.items()}


def run(sources=None):
    sources = sources or inputs()[0]
    return v2.prepare(sources, {k: v2.sha(v) for k, v in sources.items()}, now=NOW)


def test_two_useful_inert_receipts_reuse_all_roles():
    result = run()
    assert len(result["items"]) == result["max_tasks"] == 2
    a, b = [item["result"] for item in result["items"]]
    assert a["next_action"] == "VERIFY_ONE_APPROVED_SOCIAL_ENTRY"
    assert a["verified_external_visitors"] == a["revenue"] == a["commission"] == "UNKNOWN"
    assert len(b["role_handoffs"]) == 7
    assert len(b["candidate_for_similarity_review_only"]) == 1
    assert b["visual_score"] is None and b["required_visual_score"] == 9.5
    assert b["ready_for_owner_visual_review"] is False
    assert b["creative_approval"] is False
    assert result["execution_contract"]["runtime_adapter_verified"] is False
    for item in result["items"]:
        assert not item["enqueue_allowed"]
        assert item["result"]["provider_calls"] == item["result"]["cost_eur"] == 0
        assert not item["result"]["publishing_allowed"]


@pytest.mark.parametrize(
    "key,value,expected",
    [
        ("social_tagged_sessions", 1, "REVIEW_CTA_REACHABILITY_OFFLINE"),
        ("network_report_available", True, None),
        ("events", 32, None),
        ("complete", False, None),
        ("sessions", True, None),
        ("query_version", True, None),
        ("offer_views", -1, None),
        ("product_views", 100, None),
        ("unknown_sessions", 1, None),
        ("window_end", "2026-10-15T05:00:00Z", None),
        ("window_start", "2026-09-01T05:00:00Z", None),
    ],
)
def test_measurement_contract_and_action(key, value, expected):
    sources, _ = inputs()
    sources["measurement"]["value"][key] = value
    a, b = [i["result"] for i in run(sources)["items"]]
    if expected:
        assert a["next_action"] == expected
    else:
        assert a["state"] == "OWNER_HOLD"
    assert b["state"] == "INTERNAL_EDITORIAL_HANDOFF"


@pytest.mark.parametrize(
    "change", ["identity", "stale", "future", "pin", "missing_rights_inventory", "no_source"]
)
def test_editorial_hold_does_not_block_independent_first_money(change):
    sources, pins = inputs()
    if change == "identity":
        sources["editorial"]["key"] = "unapproved.source"
    elif change == "stale":
        sources["editorial"]["read_at"] = (NOW - timedelta(hours=7)).isoformat()
    elif change == "future":
        sources["editorial"]["read_at"] = (NOW + timedelta(seconds=1)).isoformat()
    elif change == "missing_rights_inventory":
        sources["inventory"]["value"]["rejected_exclusions"] = []
    elif change == "no_source":
        sources["editorial"] = None
    if change != "pin":
        pins = {k: v2.sha(v) for k, v in sources.items()}
    else:
        pins["editorial"] = "f" * 64
    a, b = [i["result"] for i in v2.prepare(sources, pins, now=NOW)["items"]]
    assert a["state"] == "INTERNAL_ACTION_RECEIPT"
    assert b["state"] == "OWNER_HOLD"


def test_old_worker_holds_preserved_no_visual_or_rights_invented():
    b = run()["items"][1]["result"]
    assert any(r["holds"] for r in b["role_handoffs"])
    assert "actual_visual_qa_9_5_required" in b["holds"]
    assert "rights_and_source_clearance_required" in b["holds"]
    assert not b["scheduled"] and not b["autonomous_creative_generation"]


def test_role_source_failure_is_not_masked_by_published_flag():
    sources, _ = inputs()
    sources["editorial"]["value"]["W6"]["hooks"] = []
    b = run(sources)["items"][1]["result"]
    assert b["state"] == "OWNER_HOLD"
    assert not b["candidate_for_similarity_review_only"]


def test_same_records_have_same_task_keys_across_fresh_reads():
    sources, _ = inputs()
    old = run(sources)
    for source in sources.values():
        source["read_at"] = (NOW - timedelta(minutes=1)).isoformat()
    new = run(sources)
    assert [i["task_key_proposal"] for i in old["items"]] == [
        i["task_key_proposal"] for i in new["items"]
    ]
    sources["editorial"]["value"]["W1"]["voice"] = "Different input"
    assert run(sources)["items"][1]["task_key_proposal"] != old["items"][1]["task_key_proposal"]


def test_private_atomic_resume_and_parallel_repetition(tmp_path):
    path, plan = tmp_path / "receipt.json", run()
    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(lambda _: v2.save_private(path, plan), range(2)))
    assert sorted(results) == ["ALREADY_PREPARED", "PREPARED"]
    before = path.read_bytes()
    assert v2.save_private(path, copy.deepcopy(plan)) == "ALREADY_PREPARED"
    assert before == path.read_bytes() and path.stat().st_mode & 0o777 == 0o600


def test_interruption_before_replace_preserves_absence_then_resumes(tmp_path, monkeypatch):
    from scripts import dufynd_content7_activation as atomic

    path, plan = tmp_path / "receipt.json", run()
    original = atomic.os.replace
    monkeypatch.setattr(
        atomic.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("synthetic"))
    )
    with pytest.raises(OSError):
        v2.save_private(path, plan)
    assert not path.exists()
    monkeypatch.setattr(atomic.os, "replace", original)
    assert v2.save_private(path, plan) == "PREPARED"


@pytest.mark.parametrize("corruption", ["truncated", "changed_result", "changed_pin"])
def test_corrupt_checkpoint_never_overwritten(tmp_path, corruption):
    path, plan = tmp_path / "receipt.json", run()
    v2.save_private(path, plan)
    saved = json.loads(path.read_text())
    if corruption == "truncated":
        path.write_text("{")
    else:
        if corruption == "changed_result":
            saved["plan"]["items"][0]["result"]["creative_approval"] = True
        else:
            saved["sha256"] = "f" * 64
        path.write_text(json.dumps(saved))
    before = path.read_bytes()
    with pytest.raises(v2.ValueHold, match="checkpoint"):
        v2.save_private(path, plan)
    assert path.read_bytes() == before


def test_repository_output_and_unsafe_plan_rejected(tmp_path):
    with pytest.raises(v2.ValueHold, match="outside_repository"):
        v2.save_private(v2.Path(v2.__file__).parent / "private.json", run())
    plan = run()
    plan["production_activation"] = True
    with pytest.raises(v2.ValueHold, match="unsafe"):
        v2.save_private(tmp_path / "bad.json", plan)


def test_no_third_task_or_unknown_source():
    sources, pins = inputs()
    sources["third"] = {}
    with pytest.raises(v2.ValueHold, match="bounded_inputs"):
        v2.prepare(sources, pins, now=NOW)


@pytest.mark.parametrize(
    "product,offer,clicks,expected",
    [
        (0, 0, 0, "REVIEW_EXISTING_PRODUCT_ENTRY"),
        (1, 0, 0, "REVIEW_OFFER_VISIBILITY_OFFLINE"),
        (1, 1, 0, "REVIEW_CTA_REACHABILITY_OFFLINE"),
        (1, 1, 1, "RECONCILE_ORIGINAL_NETWORK_REPORT"),
    ],
)
def test_one_action_per_observed_stage(product, offer, clicks, expected):
    sources, _ = inputs()
    sources["measurement"]["value"].update(
        social_tagged_sessions=1,
        product_views=product,
        offer_views=offer,
        merchant_clickouts=clicks,
    )
    assert run(sources)["items"][0]["result"]["next_action"] == expected


def test_broken_crosslinks_produce_specific_non_mutating_repair_handoff():
    sources, _ = inputs()
    sources["editorial"]["value"]["W2"]["ideas"][0]["hook"] = "Unmatched source text"
    before = copy.deepcopy(sources)
    result = run(sources)["items"][1]["result"]
    assert result["state"] == "OWNER_HOLD"
    assert result["repair_handoff"][0]["source_idea_id"] == "draft_concept_0"
    assert result["repair_handoff"][0]["hook_matches_W6"] is False
    assert sources == before


def test_nonzero_worker_cost_and_self_rehashed_unsafe_result_are_held(tmp_path, monkeypatch):
    monkeypatch.setitem(v2.HANDLERS, "W1", lambda *_: {"cost_eur": 1})
    result = run()
    assert result["items"][1]["result"]["reason"] == "worker_cost_contract_changed"
    assert result["items"][0]["result"]["state"] == "INTERNAL_ACTION_RECEIPT"
    result["items"][0]["result"]["publishing_allowed"] = True
    result["items"][0]["result_sha256"] = v2.sha(result["items"][0]["result"])
    with pytest.raises(v2.ValueHold, match="unsafe"):
        v2.save_private(tmp_path / "unsafe.json", result)
