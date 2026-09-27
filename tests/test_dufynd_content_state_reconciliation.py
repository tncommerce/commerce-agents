"""Keep DUFYND content control-plane state free of expired launch-hold actions."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.refresh_scentai_jarvis_state import refresh_state

STRATEGY = Path("examples/retail/data/dufynd_content_strategy.json")
PIPELINE = Path("examples/retail/data/scentai_content_pipeline_status.json")
MASTER = Path("examples/retail/data/scentai_jarvis_master_status.json")

NEXT_ACTION = "reconcile_live_social_state_before_next_content_action"
NEXT_ACTION_CLASS = "manual_state_reconciliation_required"


def test_content_strategy_requires_social_state_reconciliation_after_launch_hold() -> None:
    strategy = json.loads(STRATEGY.read_text(encoding="utf-8"))

    assert strategy["strategy_status"] == "state_reconciliation_required"
    assert strategy["next_action"] == NEXT_ACTION
    assert strategy["next_action_class"] == NEXT_ACTION_CLASS
    assert strategy["user_approval_required_now"] is False
    assert "wait_for_2026_09_26" not in strategy["next_action"]
    assert "publishing" in strategy["approval_gates"]
    assert "reconcile_live_social_publish_state" in strategy["waiting_on"]


def test_derived_content_control_plane_matches_reconciliation_state() -> None:
    pipeline = json.loads(PIPELINE.read_text(encoding="utf-8"))
    master = json.loads(MASTER.read_text(encoding="utf-8"))

    assert pipeline["next_action"] == NEXT_ACTION
    assert pipeline["next_action_class"] == NEXT_ACTION_CLASS
    assert pipeline["user_approval_required_now"] is False

    content_domain = master["domains"]["content"]
    assert content_domain["next_action"] == NEXT_ACTION
    assert content_domain["next_action_class"] == NEXT_ACTION_CLASS
    assert content_domain["user_approval_required_now"] is False


def test_reconciliation_state_does_not_authorize_social_publish() -> None:
    strategy = json.loads(STRATEGY.read_text(encoding="utf-8"))
    master = json.loads(MASTER.read_text(encoding="utf-8"))

    assert "This state does not authorize publishing." in strategy["reason"]
    assert master["safety"]["automatic_social_publish_allowed"] is False

def test_master_fingerprint_matches_rebuilt_control_plane() -> None:
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    expected = refresh_state(generated_at=master["generated_at"])["master_status"]

    assert master["source_fingerprint_sha256"] == expected["source_fingerprint_sha256"]

