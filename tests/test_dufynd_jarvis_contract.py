from __future__ import annotations

import json
from pathlib import Path


CONTRACT_PATH = (
    Path(__file__).parents[1]
    / "examples"
    / "retail"
    / "data"
    / "dufynd_jarvis_contract.json"
)


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_dufynd_jarvis_contract_has_current_brand_and_version() -> None:
    contract = load_contract()

    assert contract["brand"] == "DUFYND"
    assert contract["operator"] == "TNCommerce"
    assert contract["version"] == "2.0"


def test_dufynd_jarvis_contract_exposes_required_learning_surfaces() -> None:
    contract = load_contract()
    rpc = contract["rpc"]

    assert rpc["operating_context"] == "get_dufynd_jarvis_context"
    assert rpc["creative_context"] == "get_dufynd_jarvis_creative_context"
    assert rpc["autonomy_queue"] == "get_dufynd_autonomy_queue"
    assert rpc["experiment_rubric"] == "get_dufynd_experiment_rubric"
    assert rpc["content_board_learning"] == "get_dufynd_content_board_learning"

    required_sections = set(contract["required_context_sections"])
    assert {
        "creative_patterns",
        "pattern_learning",
        "content_board",
        "experiment_rubric",
        "autonomy_queue",
        "approval_rules",
    } <= required_sections


def test_dufynd_jarvis_contract_keeps_high_impact_actions_human_gated() -> None:
    contract = load_contract()
    gates = set(contract["human_approval_gates"])

    assert "spending money" in gates
    assert "publishing content" in gates
    assert "merging production-affecting code" in gates


def test_dufynd_jarvis_contract_has_full_experiment_feedback_loop() -> None:
    contract = load_contract()
    metrics = set(contract["experiment_metrics"])

    assert {
        "scroll_stop",
        "product_accuracy",
        "luxury_feel",
        "brand_fit",
        "reproducibility",
        "conversion_fit",
    } <= metrics
