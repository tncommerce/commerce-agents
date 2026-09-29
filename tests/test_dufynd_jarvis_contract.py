import json

CONTRACT_PATH = "examples/retail/data/dufynd_jarvis_contract.json"


def load_contract() -> dict:
    with open(CONTRACT_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def test_dufynd_jarvis_contract_has_current_brand_and_version() -> None:
    contract = load_contract()

    assert contract["brand"] == "DUFYND"
    assert contract["operator"] == "TNCommerce"
    assert contract["version"] == "3.0"


def test_dufynd_jarvis_contract_exposes_required_learning_surfaces() -> None:
    contract = load_contract()
    rpc = contract["rpc"]

    assert rpc["operating_context"] == "get_dufynd_jarvis_context"
    assert rpc["creative_context"] == "get_dufynd_jarvis_creative_context"
    assert rpc["autonomy_queue"] == "get_dufynd_autonomy_queue"
    assert rpc["experiment_rubric"] == "get_dufynd_experiment_rubric"
    assert rpc["content_board_learning"] == "get_dufynd_content_board_learning"
    assert rpc["pending_decisions"] == "get_dufynd_pending_decisions"
    assert rpc["health"] == "get_dufynd_jarvis_health"

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


def test_dufynd_jarvis_contract_keeps_active_runtime_off_by_default() -> None:
    contract = load_contract()
    runtime = contract["active_runtime"]

    assert runtime["default"] == "disabled"
    assert runtime["activation_env"] == "DUFYND_JARVIS_ACTIVE=1"
    assert runtime["default_max_turns"] <= runtime["hard_max_turns"]
    assert runtime["default_max_budget_usd"] <= runtime["hard_max_budget_usd"]
    assert runtime["initial_budget_window"]["status"] == "planned"
    assert runtime["initial_budget_window"]["max_runs"] == 10

    supervisor = runtime["supervisor_mode"]
    assert supervisor["status"] == "available_guarded"
    assert supervisor["default_max_events"] == 8
    assert supervisor["hard_max_events"] == 20
    assert "runtime_or_budget_gate" in supervisor["stop_conditions"]

    safe_worker = runtime["safe_worker_mode"]
    assert safe_worker["command"] == "--process-safe-task"
    assert "WebSearch" in safe_worker["builtin_tools_allowed"]
    assert "Bash" in safe_worker["builtin_tools_denied"]
    assert "Write" in safe_worker["builtin_tools_denied"]
    assert "must not mark a task done automatically" in safe_worker["task_progress_rule"]

    branch_worker = runtime["branch_worker_mode"]
    assert branch_worker["command"] == "--process-branch-task"
    assert branch_worker["push_allowed"] is False
    assert branch_worker["merge_allowed"] is False
    assert "Write" in branch_worker["builtin_tools_allowed"]
    assert "Bash" in branch_worker["builtin_tools_denied"]

    pr_orchestration = branch_worker["pr_orchestration"]
    assert pr_orchestration["mode"] == "process-branch-task-pr"
    assert pr_orchestration["target_base"] == "scentai-mvp"
    assert pr_orchestration["auto_merge"] is False
    assert pr_orchestration["main_branch_allowed"] is False
    assert "does not persist GitHub credentials" in pr_orchestration["credential_rule"]

    validation = branch_worker["validation"]
    assert "pytest -q" in validation["python"]
    assert "build acme-retail-storefront-web" in validation["storefront_when_changed"]
    assert "visual QA" in validation["rule"]

    control_plane_sync = runtime["control_plane_sync"]
    assert control_plane_sync["status"] == "required_before_active_processing"
    assert control_plane_sync["snapshot_key"] == "jarvis.repo_state_snapshot"
    assert control_plane_sync["dry_run_default"] is True

    autonomous_cycle = runtime["autonomous_cycle"]
    assert autonomous_cycle["command"] == "--autonomous-cycle"
    assert autonomous_cycle["activation_env"] == "DUFYND_JARVIS_AUTONOMOUS=1"
    assert autonomous_cycle["default_max_inbox_events"] == 2
    assert autonomous_cycle["hard_max_inbox_events"] == 5
    assert "cannot create, enlarge, reactivate or bypass" in autonomous_cycle["financial_rule"]
    assert autonomous_cycle["scheduling"].startswith("No recurring schedule")
    assert autonomous_cycle["worker_routing"]["engineering"] == "branch_worker"
    assert autonomous_cycle["worker_routing"]["non_engineering"] == "safe_worker"
    assert "cannot push, merge, deploy, publish, spend money" in autonomous_cycle["safety"]

    nightshift = runtime["nightshift_orchestrator"]
    assert nightshift["mode"] == "nightshift-pilot"
    assert nightshift["task_driven"] is True
    assert nightshift["polling_loop"] is False
    assert nightshift["default_max_tasks"] == 8
    assert nightshift["hard_max_tasks"] == 20
    assert nightshift["worker_routing"]["engineering"] == "isolated_branch_worker"
    assert nightshift["yellow_handoff"].endswith("They are never auto-merged.")
    assert nightshift["scheduling"].startswith("No recurring schedule")
    assert nightshift["main_branch_allowed"] is False
    assert "inbox events before repo-current task selection" in nightshift["event_order"]
    assert nightshift["policy_source"].endswith("scentai_jarvis_operating_policy.json")

    policy = contract["nightshift_policy"]
    assert "spend_money" in policy["action_classes"]["red_owner_only"]
    assert "production_relevant_pull_request" in policy["action_classes"]["yellow_prepare_only"]
    assert "tests_and_quality_assurance" in policy["action_classes"]["green_auto_execute"]
    assert policy["main_branch_allowed"] is False
