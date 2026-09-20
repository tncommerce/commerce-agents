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
                    "asset_business_performance": [{"asset_id": "asset1", "content_id": "video1"}],
                    "launch_gate": {
                        "state": "not_ready",
                        "required_passed": 4,
                        "required_total": 11,
                    },
                },
            )

        if request.url.path.endswith("/rpc/get_dufynd_rnd_gate"):
            return httpx.Response(
                200,
                json={
                    "state": "not_ready",
                    "passed": 3,
                    "total": 9,
                    "human_pending": 3,
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
                    "human_pending": 3,
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
    assert summary.hook_templates == 1
    assert summary.model_profiles == 1
    assert summary.ideas == 1
    assert summary.lessons == 1
    assert summary.affiliate_partners == 2
    assert summary.funnel_rows == 1
    assert summary.asset_performance_rows == 1


def test_bridge_loads_launch_gate() -> None:
    bridge = DufyndJarvisBridge(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        transport=mock_transport(),
    )

    gate = bridge.load_launch_gate()

    assert gate["state"] == "not_ready"
    assert gate["required_passed"] == 4


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
    assert gate["human_pending"] == 3


def test_bridge_refreshes_rnd_gate() -> None:
    bridge = DufyndJarvisBridge(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        transport=mock_transport(),
    )

    gate = bridge.refresh_rnd_gate()

    assert gate["state"] == "not_ready"
    assert gate["total"] == 9
