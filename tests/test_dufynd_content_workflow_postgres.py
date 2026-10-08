"""Revision/CAS/QA gates on CI's disposable Postgres; never creates live assets."""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated PostgreSQL service required")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module", autouse=True)
def schema():
    if not DSN:
        yield
        return
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("""
          alter table public.dufynd_human_decisions
           add column action_type text, add column title text, add column question text,
           add column decision_token text, add column context jsonb,
           add column updated_at timestamptz default now();
          create table public.dufynd_content_assets(
            id text primary key, version int default 1, uri text, content_id text,
            platform text, status text, metadata jsonb default '{}');
        """)
        for pattern in (
            "*content_candidate_owner_gate_v1.sql",
            "*content_publish_quality_gate_v2.sql",
            "*content_workflow_control_plane.sql",
            "*_dufynd_production_audio_gate.sql",
        ):
            c.execute(next((ROOT / "supabase/migrations").glob(pattern)).read_text())
    yield


@pytest.fixture
def db():
    import psycopg

    with psycopg.connect(DSN) as c:
        yield c
        c.rollback()


def asset(c):
    aid = "qa_" + uuid4().hex
    c.execute(
        "insert into dufynd_content_assets(id,uri,content_id,platform,status) values(%s,'fixture://only','qa','instagram','draft')",
        (aid,),
    )
    return aid


def advance(c, aid, expected, target, proof=None):
    return c.execute(
        "select advance_dufynd_content_workflow(%s,%s,%s,%s::jsonb)",
        (aid, expected, target, json.dumps(proof or {})),
    ).fetchone()[0]


def proof(c, aid, **extra):
    fp = c.execute("select dufynd_content_revision(%s)", (aid,)).fetchone()[0]
    return {
        "status": "pass",
        "revision_fingerprint": fp,
        "observed_at": "2026-01-01T00:00:00Z",
        "evidence_ref": "qa_verified_fixture",
        **extra,
    }


def test_cas_missing_proof_generator_fail_closed_and_revision_reset(db):
    aid = asset(db)
    assert advance(db, aid, None, "owner_review_ready")["reason"] == "workflow_not_started"
    assert advance(db, aid, None, "brief_ready")["advanced"]
    assert advance(db, aid, "rights_verified", "creative_requested")["reason"] == "state_conflict"
    assert (
        advance(db, aid, "brief_ready", "product_truth_verified")["reason"]
        == "missing_revision_evidence"
    )
    assert advance(
        db, aid, "brief_ready", "product_truth_verified", {"product_truth": proof(db, aid)}
    )["advanced"]
    assert advance(
        db, aid, "product_truth_verified", "rights_verified", {"rights": proof(db, aid)}
    )["advanced"]
    assert (
        advance(db, aid, "rights_verified", "creative_requested")["generator_dispatched"] is False
    )
    assert (
        db.execute(
            "select blocker from dufynd_content_workflows where asset_id=%s", (aid,)
        ).fetchone()[0]
        == "approved_free_generator_unavailable"
    )
    db.execute("update dufynd_content_assets set version=2 where id=%s", (aid,))
    assert (
        advance(
            db, aid, "creative_requested", "creative_received", {"creative_receipt": proof(db, aid)}
        )["reason"]
        == "qa_revision_changed"
    )
    assert (
        db.execute(
            "select evidence from dufynd_content_workflows where asset_id=%s", (aid,)
        ).fetchone()[0]
        == {}
    )


@pytest.mark.parametrize(
    "missing",
    [
        "product_truth",
        "rights",
        "product_fidelity",
        "dimensions",
        "mobile_preview",
        "factual_copy",
        "click_path",
        "visual_quality",
    ],
)
def test_no_owner_gate_when_any_revision_check_fails(db, missing):
    aid = asset(db)
    advance(db, aid, None, "brief_ready")
    checks = {
        k: proof(db, aid)
        for k in (
            "product_truth",
            "rights",
            "product_fidelity",
            "dimensions",
            "mobile_preview",
            "factual_copy",
            "click_path",
            "visual_quality",
        )
    }
    checks["visual_quality"]["score"] = 9.7
    checks[missing]["status"] = "fail"
    db.execute(
        "update dufynd_content_workflows set evidence=%s::jsonb where asset_id=%s",
        (json.dumps(checks), aid),
    )
    assert (
        db.execute("select dufynd_content_workflow_qa_reason(%s)", (aid,)).fetchone()[0]
        == "qa_missing_or_failed_" + missing
    )
    assert (
        db.execute("select request_dufynd_content_owner_review(%s)", (aid,)).fetchone()[0]["ready"]
        is False
    )
    assert (
        db.execute(
            "select count(*) from dufynd_human_decisions where context->'candidate'->>'asset_reference'=%s",
            (aid,),
        ).fetchone()[0]
        == 0
    )


@pytest.mark.parametrize("score", [9.49, 10.1, "NaN", None])
def test_score_cannot_override_floor_or_proofs(db, score):
    aid = asset(db)
    advance(db, aid, None, "brief_ready")
    checks = {
        k: proof(db, aid)
        for k in (
            "product_truth",
            "rights",
            "product_fidelity",
            "dimensions",
            "mobile_preview",
            "factual_copy",
            "click_path",
            "visual_quality",
        )
    }
    checks["visual_quality"]["score"] = score
    db.execute(
        "update dufynd_content_workflows set evidence=%s::jsonb where asset_id=%s",
        (json.dumps(checks), aid),
    )
    assert (
        db.execute("select dufynd_content_workflow_qa_reason(%s)", (aid,)).fetchone()[0]
        == "qa_visual_score_below_9_5"
    )


def test_owner_approval_and_external_progress_cannot_be_simulated(db):
    aid = asset(db)
    advance(db, aid, None, "brief_ready")
    db.execute(
        "update dufynd_content_workflows set state='owner_review_ready' where asset_id=%s", (aid,)
    )
    assert (
        advance(db, aid, "owner_review_ready", "owner_approved", {"owner_go": True})["reason"]
        == "owner_go_missing"
    )
    assert advance(db, aid, "owner_review_ready", "published")["reason"] == "transition_forbidden"
    assert (
        db.execute(
            "select count(*) from dufynd_human_decisions where status='approved' and context->'candidate'->>'asset_reference'=%s",
            (aid,),
        ).fetchone()[0]
        == 0
    )
    assert not db.execute(
        "select has_function_privilege('anon','advance_dufynd_content_workflow(text,text,text,jsonb)','execute')"
    ).fetchone()[0]


def test_complete_candidate_stops_at_real_owner_then_observes_external_evidence(db):
    aid = "qa_" + uuid4().hex
    meta = {
        **{
            k: "pass"
            for k in (
                "quality_review",
                "visual_qa",
                "rights_review",
                "product_match_review",
                "destination_review",
            )
        },
        "asset_sha256": "a" * 64,
        "review_asset_sha256": "a" * 64,
        "review_evidence_ref": "qa_fixture",
        "creator_actor_id": "qa_creator",
        "internal_reviewer_actor_id": "qa_checker",
        "campaign_id": "qa_exp",
        "product_id": "SC-TEST-100",
        "content_kind": "meme",
        "publication_checks_v3": {
            k: {"passed": True, "asset_sha256": "a" * 64, "evidence_ref": "qa:quality"}
            for k in (
                "duplicate_content",
                "safe_zones",
                "sharpness_compression",
                "platform_caption",
                "sound_timing",
            )
        },
        "publish_contract_v2": {
            "media_kind": "image",
            "width_px": 1080,
            "height_px": 1350,
            "visual_score": 9.7,
            "native_preview_verified": True,
            "final_upload_asset_verified": True,
            "cta_mode": "profile_link",
            "profile_link_verified": True,
            "audio_contract": {
                "mode": "instagram_native_music",
                "delivery": "instagram_native_app",
                "commercial_rights_evidence_ref": "qa:rights",
                "audible_preview_evidence_ref": "qa:listen",
                "audible_preview_verified": True,
                "commercial_music_rights_verified": True,
                "audio_score": 9.7,
                "native_track_selected_and_preheard": True,
            },
        },
        "owner_review_v1": {
            "internal_ready": True,
            "product": "QA fixture only",
            "product_id": "SC-TEST-100",
            "hook": "Fixture hook",
            "caption": "Fixture caption",
            "reason": "Disposable test",
            "platform": "instagram",
            "requested_at": "2099-01-01T00:00:00Z",
            "content_id": "qa_content",
            "experiment_id": "qa_exp",
            "internal_rating": 9.7,
        },
    }
    db.execute(
        "insert into dufynd_content_assets(id,uri,content_id,platform,status,metadata) values(%s,'fixture://only','qa_content','instagram','internally_ready',%s::jsonb)",
        (aid, json.dumps(meta)),
    )
    advance(db, aid, None, "brief_ready")
    assert (
        db.execute(
            "select count(*) from dufynd_human_decisions where status='pending' and context->'candidate'->>'asset_reference'=%s",
            (aid,),
        ).fetchone()[0]
        == 0
    )
    for old, new, key in (
        ("brief_ready", "product_truth_verified", "product_truth"),
        ("product_truth_verified", "rights_verified", "rights"),
    ):
        assert advance(db, aid, old, new, {key: proof(db, aid)})["advanced"]
    advance(db, aid, "rights_verified", "creative_requested")
    assert advance(
        db, aid, "creative_requested", "creative_received", {"creative_receipt": proof(db, aid)}
    )["advanced"]
    checks = {
        k: proof(db, aid)
        for k in (
            "product_truth",
            "rights",
            "product_fidelity",
            "dimensions",
            "mobile_preview",
            "factual_copy",
            "click_path",
            "visual_quality",
        )
    }
    checks["visual_quality"]["score"] = 9.7
    assert advance(db, aid, "creative_received", "quality_pass", checks)["advanced"]
    assert advance(
        db, aid, "quality_pass", "mobile_preview_pass", {"mobile_preview": proof(db, aid)}
    )["advanced"]
    assert advance(
        db, aid, "mobile_preview_pass", "click_path_pass", {"click_path": proof(db, aid)}
    )["advanced"]
    assert advance(db, aid, "click_path_pass", "owner_review_ready")["advanced"]
    did = db.execute(
        "select owner_decision_id from dufynd_content_workflows where asset_id=%s", (aid,)
    ).fetchone()[0]
    assert (
        db.execute(
            "select status from dufynd_human_decisions where decision_id=%s", (did,)
        ).fetchone()[0]
        == "pending"
    )
    assert advance(db, aid, "owner_review_ready", "owner_approved")["reason"] == "owner_go_missing"
    # Test-only owner action, rolled back with this fixture; never performed by the RPC.
    db.execute("update dufynd_human_decisions set status='approved' where decision_id=%s", (did,))
    assert advance(db, aid, "owner_review_ready", "owner_approved")["advanced"]
    assert advance(db, aid, "owner_approved", "scheduled")["reason"] == "missing_revision_evidence"
    result = advance(
        db, aid, "owner_approved", "scheduled", {"schedule_observation": proof(db, aid)}
    )
    assert result["advanced"] and result["publishing_authorized"] is False
    assert (
        db.execute("select metadata from dufynd_content_assets where id=%s", (aid,)).fetchone()[0]
        == meta
    )


def test_auto_revision_is_bounded_and_does_not_dispatch_generator(db):
    aid = asset(db)
    advance(db, aid, None, "brief_ready")
    db.execute(
        "update dufynd_content_workflows set state='creative_received' where asset_id=%s", (aid,)
    )
    for _ in range(3):
        assert advance(db, aid, "creative_received", "self_review_failed")["advanced"]
        assert (
            advance(db, aid, "self_review_failed", "auto_revision_requested")[
                "generator_dispatched"
            ]
            is False
        )
        assert advance(
            db,
            aid,
            "auto_revision_requested",
            "creative_received",
            {"creative_receipt": proof(db, aid)},
        )["advanced"]
    advance(db, aid, "creative_received", "self_review_failed")
    assert (
        advance(db, aid, "self_review_failed", "auto_revision_requested")["reason"]
        == "revision_limit_reached"
    )


def test_production_audio_contract_matrix(db):
    db.execute((ROOT / "tests/sql_dufynd_audio_gate.sql").read_text())


def test_post_publication_requires_verified_public_sound(db):
    aid = asset(db)
    advance(db, aid, None, "brief_ready")
    db.execute("update dufynd_content_workflows set state='published' where asset_id=%s", (aid,))
    evidence = {"publication_verification": proof(db, aid)}
    assert advance(db, aid, "published", "publication_verified", evidence)["reason"] == (
        "public_audio_playback_evidence_required"
    )
