from __future__ import annotations

import json

import httpx
import pytest
from scripts.dufynd_jarvis_bridge import (
    DufyndJarvisBridge,
    summarize_context,
)


def mock_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/rpc/get_dufynd_jarvis_context"):
            return httpx.Response(
                200,
                json={
                    "references": [{"id": "ex1"}, {"id": "ex2"}],
                    "formats": [{"id": "genesis"}],
                    "creative_patterns": [{"pattern_id": "macro"}],
                    "hook_templates": [{"id": "hook1"}],
                    "model_profiles": [{"model_id": "seedance"}],
                    "ideas": [{"id": "idea1"}],
                    "lessons": [{"id": "lesson1"}],
                    "recent_experiments": [],
                    "affiliate_partners": [
                        {"merchant_id": "douglas"},
                        {"merchant_id": "notino"},
                    ],
                    "content_funnel": [{"content_id": "video1"}],
                    "content_board": [{"slot": 1}, {"slot": 2}],
                    "asset_business_performance": [{"asset_id": "asset1", "content_id": "video1"}],
                    "autonomy_queue": {
                        "safe_to_execute": [{"task_id": "task_safe"}],
                        "approval_required": [{"task_id": "task_approval"}],
                    },
                    "experiment_rubric": [
                        {"metric_id": "scroll_stop"},
                        {"metric_id": "product_accuracy"},
                    ],
                    "launch_gate": {
                        "state": "not_ready",
                        "required_passed": 4,
                        "required_total": 11,
                    },
                },
            )

        if request.url.path.endswith("/rpc/get_dufynd_jarvis_creative_context"):
            return httpx.Response(
                200,
                json={
                    "idea_generation": {
                        "formats": [{"id": "genesis"}],
                        "patterns": [{"pattern_id": "macro"}],
                    },
                    "references": [{"id": "ex1"}],
                    "reference_patterns": [],
                    "idea_patterns": [],
                    "recent_experiments": [],
                    "recent_performance": [],
                    "autonomy_queue": {
                        "safe_to_execute": [{"task_id": "task_safe"}],
                    },
                },
            )

        if request.url.path.endswith("/rpc/get_dufynd_autonomy_queue"):
            return httpx.Response(
                200,
                json={
                    "safe_to_execute": [{"task_id": "task_safe"}],
                    "in_progress": [{"task_id": "task_running"}],
                    "waiting_human_input": [{"task_id": "task_input"}],
                    "waiting_external": [{"task_id": "task_external"}],
                    "approval_required": [{"task_id": "task_approval"}],
                    "done_recent": [],
                },
            )

        if request.url.path.endswith("/rpc/get_dufynd_pending_decisions"):
            return httpx.Response(
                200,
                json=[
                    {
                        "decision_id": "decision_test",
                        "decision_token": "GO-TEST",
                        "status": "pending",
                    }
                ],
            )

        if request.url.path.endswith("/rpc/claim_dufynd_jarvis_event"):
            return httpx.Response(
                200,
                json={
                    "inbox_id": 7,
                    "event_type": "creative_reference_added",
                    "status": "processing",
                    "attempts": 1,
                },
            )

        if request.url.path.endswith("/rpc/complete_dufynd_jarvis_event"):
            row = json.loads(request.content)
            assert row["p_inbox_id"] == 7
            assert row["p_status"] == "done"
            return httpx.Response(
                200,
                json={
                    "inbox_id": 7,
                    "event_type": "creative_reference_added",
                    "status": "done",
                    "attempts": 1,
                },
            )

        if request.url.path.endswith("/rpc/get_dufynd_experiment_rubric"):
            return httpx.Response(
                200,
                json=[
                    {
                        "metric_id": "scroll_stop",
                        "weight": 1.25,
                        "hard_fail_below": 5,
                        "target_score": 8.5,
                    },
                    {
                        "metric_id": "product_accuracy",
                        "weight": 1.4,
                        "hard_fail_below": 8,
                        "target_score": 9.5,
                    },
                ],
            )

        if request.url.path.endswith("/rpc/get_dufynd_rnd_gate"):
            return httpx.Response(
                200,
                json={
                    "state": "not_ready",
                    "passed": 3,
                    "total": 9,
                    "human_pending": 4,
                    "checks": [],
                },
            )

        if request.url.path.endswith("/rpc/refresh_dufynd_rnd_gate"):
            return httpx.Response(
                200,
                json={
                    "state": "not_ready",
                    "passed": 3,
                    "total": 9,
                    "human_pending": 4,
                    "checks": [],
                },
            )

        if request.url.path.endswith("/rpc/get_dufynd_launch_gate"):
            return httpx.Response(
                200,
                json={
                    "state": "not_ready",
                    "required_passed": 4,
                    "required_total": 11,
                    "checks": [],
                },
            )

        if request.url.path.endswith("/rpc/refresh_dufynd_launch_gate"):
            return httpx.Response(
                200,
                json={
                    "state": "not_ready",
                    "required_passed": 4,
                    "required_total": 11,
                    "checks": [],
                },
            )

        if request.url.path.endswith("/dufynd_creative_references"):
            row = json.loads(request.content)
            assert row["label"] == "Reference 99"
            assert row["status"] == "candidate_reference"
            return httpx.Response(201)

        if request.url.path.endswith("/dufynd_creative_patterns"):
            row = json.loads(request.content)
            assert row["name"] == "Camera Dive"
            assert row["role"] == "camera"
            return httpx.Response(201)

        if request.url.path.endswith("/dufynd_reference_patterns"):
            row = json.loads(request.content)
            assert row["reference_id"] == "reference_test"
            assert row["pattern_id"] == "pattern_test"
            assert row["confidence"] == 1.0
            assert request.url.params["on_conflict"] == "reference_id,pattern_id"
            assert "resolution=merge-duplicates" in request.headers["prefer"]
            return httpx.Response(201)

        if request.url.path.endswith("/dufynd_idea_patterns"):
            row = json.loads(request.content)
            assert row["idea_id"] == "idea_test"
            assert row["position"] == 1
            assert request.url.params["on_conflict"] == "idea_id,pattern_id,role"
            return httpx.Response(201)

        if request.url.path.endswith("/dufynd_knowledge_events"):
            row = json.loads(request.content)
            assert row["event_type"] == "reference_ingested"
            assert row["payload"]["patterns_added"] == 1
            return httpx.Response(201)

        if request.url.path.endswith("/dufynd_agent_runs"):
            row = json.loads(request.content)
            assert row["agent_name"] == "jarvis"
            assert row["run_type"] == "creative_review"
            assert row["human_approval_required"] is False
            return httpx.Response(201)

        if request.url.path.endswith("/dufynd_content_ideas"):
            row = json.loads(request.content)
            assert row["title"] == "Notes Become the Bottle"
            assert row["priority"] == 100
            assert row["status"] == "draft"
            return httpx.Response(201)

        if request.url.path.endswith("/dufynd_content_assets"):
            row = json.loads(request.content)
            assert row["content_id"] == "genesis_naxos_01"
            assert row["status"] == "draft"
            return httpx.Response(201)

        if request.url.path.endswith("/dufynd_experiments"):
            row = json.loads(request.content)
            assert row["model"] == "seedance"
            assert row["scores"]["scroll_stop"] == 8.5
            return httpx.Response(201)

        if request.url.path.endswith("/dufynd_agent_lessons"):
            row = json.loads(request.content)
            assert row["domain"] == "creative"
            assert row["confidence"] == 1.0
            return httpx.Response(201)

        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_bridge_loads_context_and_summary() -> None:
    bridge = DufyndJarvisBridge(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        transport=mock_transport(),
    )

    context = bridge.load_context()
    summary = summarize_context(context)

    assert summary.launch_state == "not_ready"
    assert summary.references == 2
    assert summary.formats == 1
    assert summary.creative_patterns == 1
    assert summary.hook_templates == 1
    assert summary.model_profiles == 1
    assert summary.ideas == 1
    assert summary.lessons == 1
    assert summary.affiliate_partners == 2
    assert summary.funnel_rows == 1
    assert summary.asset_performance_rows == 1
    assert summary.content_board_items == 2
    assert summary.autonomy_ready == 1
    assert summary.autonomy_approval_required == 1
    assert summary.rubric_metrics == 2


def test_bridge_loads_creative_context() -> None:
    bridge = DufyndJarvisBridge(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        transport=mock_transport(),
    )

    context = bridge.load_creative_context()

    assert context["idea_generation"]["formats"][0]["id"] == "genesis"
    assert context["idea_generation"]["patterns"][0]["pattern_id"] == "macro"
    assert context["autonomy_queue"]["safe_to_execute"][0]["task_id"] == "task_safe"


def test_bridge_loads_autonomy_queue() -> None:
    bridge = DufyndJarvisBridge(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        transport=mock_transport(),
    )

    queue = bridge.load_autonomy_queue()

    assert len(queue["safe_to_execute"]) == 1
    assert len(queue["approval_required"]) == 1
    assert len(queue["waiting_external"]) == 1


def test_bridge_loads_pending_decisions() -> None:
    bridge = DufyndJarvisBridge(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        transport=mock_transport(),
    )

    decisions = bridge.load_pending_decisions()

    assert decisions[0]["decision_token"] == "GO-TEST"
    assert decisions[0]["status"] == "pending"


def test_bridge_claims_and_completes_inbox_event() -> None:
    bridge = DufyndJarvisBridge(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        transport=mock_transport(),
    )

    event = bridge.claim_next_inbox_event()
    completed = bridge.complete_inbox_event(inbox_id=7)

    assert event is not None
    assert event["inbox_id"] == 7
    assert event["status"] == "processing"
    assert completed["status"] == "done"


def test_bridge_loads_experiment_rubric() -> None:
    bridge = DufyndJarvisBridge(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        transport=mock_transport(),
    )

    rubric = bridge.load_experiment_rubric()

    assert len(rubric) == 2
    assert rubric[1]["metric_id"] == "product_accuracy"
    assert rubric[1]["hard_fail_below"] == 8


def test_bridge_loads_launch_gate() -> None:
    bridge = DufyndJarvisBridge(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        transport=mock_transport(),
    )

    gate = bridge.load_launch_gate()

    assert gate["state"] == "not_ready"
    assert gate["required_passed"] == 4


def test_bridge_records_reference_and_pattern_links() -> None:
    bridge = DufyndJarvisBridge(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        transport=mock_transport(),
    )

    reference_id = bridge.record_creative_reference(
        label="Reference 99",
        category="camera_transition",
        summary="Camera enters one material world and exits another.",
        dufynd_application="Use the move as a scent-world transition.",
        quality_notes="Keep spatial continuity.",
        reference_id="reference_test",
    )
    pattern_id = bridge.record_creative_pattern(
        name="Camera Dive",
        role="camera",
        description="Camera physically enters a foreground object.",
        mechanism="A motivated camera move creates a hidden transition.",
        pattern_id="pattern_test",
    )
    bridge.link_reference_pattern(
        reference_id=reference_id,
        pattern_id=pattern_id,
        confidence=1.3,
    )
    bridge.link_idea_pattern(
        idea_id="idea_test",
        pattern_id=pattern_id,
        role="camera",
        position=0,
    )
    bridge.record_knowledge_event(
        event_type="reference_ingested",
        source_type="operator_reference",
        source_id=reference_id,
        payload={"patterns_added": 1},
    )

    assert reference_id == "reference_test"
    assert pattern_id == "pattern_test"


def test_bridge_records_agent_run() -> None:
    bridge = DufyndJarvisBridge(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        transport=mock_transport(),
    )

    bridge.record_run(
        run_type="creative_review",
        input_summary="Reference analysis",
        output_summary="Stored new creative rules",
    )


def test_bridge_requires_server_credentials() -> None:
    with pytest.raises(ValueError, match="SUPABASE_URL"):
        DufyndJarvisBridge(
            supabase_url="",
            secret_key="",
        )


def test_bridge_records_creative_learning_entities() -> None:
    bridge = DufyndJarvisBridge(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        transport=mock_transport(),
    )

    idea_id = bridge.record_content_idea(
        title="Notes Become the Bottle",
        concept="Sensory world resolves into the fragrance.",
        hook="Guess the fragrance from three notes.",
        priority=140,
        idea_id="idea_test",
    )
    experiment_id = bridge.record_experiment(
        model="seedance",
        prompt_summary="Macro notes into bottle reveal.",
        verdict="promising",
        scores={"scroll_stop": 8.5},
        experiment_id="exp_test",
    )
    lesson_id = bridge.record_lesson(
        domain="creative",
        lesson="Protect the packshot.",
        evidence="Label drift in generative tests.",
        action_rule="Use deterministic final product frames.",
        confidence=1.4,
        lesson_id="lesson_test",
    )

    assert idea_id == "idea_test"
    assert experiment_id == "exp_test"
    assert lesson_id == "lesson_test"


def test_bridge_refreshes_launch_gate() -> None:
    bridge = DufyndJarvisBridge(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        transport=mock_transport(),
    )

    gate = bridge.refresh_launch_gate()

    assert gate["state"] == "not_ready"
    assert gate["required_total"] == 11


def test_bridge_records_content_asset() -> None:
    bridge = DufyndJarvisBridge(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        transport=mock_transport(),
    )

    asset_id = bridge.record_content_asset(
        content_idea_id="idea_test",
        asset_type="video",
        uri="https://example.test/video.mp4",
        platform="tiktok",
        metadata={"tier": "hero"},
        content_id="genesis_naxos_01",
        asset_id="asset_test",
    )

    assert asset_id == "asset_test"


def test_bridge_loads_rnd_gate() -> None:
    bridge = DufyndJarvisBridge(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        transport=mock_transport(),
    )

    gate = bridge.load_rnd_gate()

    assert gate["state"] == "not_ready"
    assert gate["passed"] == 3
    assert gate["human_pending"] == 4


def test_bridge_refreshes_rnd_gate() -> None:
    bridge = DufyndJarvisBridge(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        transport=mock_transport(),
    )

    gate = bridge.refresh_rnd_gate()

    assert gate["state"] == "not_ready"
    assert gate["total"] == 9
