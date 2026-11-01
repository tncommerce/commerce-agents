"""Default-branch Awin workflow registers ONLY the existing branch-gated review choices."""

from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/dufynd-awin-feed-revalidation.yml")


def test_manual_action_selector_is_complete_without_default_execution() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    config = yaml.load(raw, Loader=yaml.BaseLoader)
    assert list(config["on"]) == ["workflow_dispatch"]
    inputs = config["on"]["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"inventory_task"}
    task = inputs["inventory_task"]
    assert task["type"] == "choice"
    assert task["required"] == "true"
    assert task["default"] == "perfumetrader_inventory"
    assert set(task["options"]) == {
        "perfumetrader_inventory",
        "top_parfuemerie_review",
        "perfumetrader_private_catalog",
    }
    assert len(task["options"]) == 3
    assert config["permissions"] == {}
    assert set(config["jobs"]) == {"require-reviewed-branch"}
    job = config["jobs"]["require-reviewed-branch"]
    assert job["timeout-minutes"] == "1"
    steps = job["steps"]
    assert len(steps) == 1 and "exit 2" in steps[0]["run"]
    assert "Select branch scentai-mvp" in steps[0]["run"]
    assert "github.token" not in raw
    assert "secrets." not in raw
    assert "schedule:" not in raw
    assert "push:" not in raw
    assert "AWIN_DATA_FEED_API_KEY" not in raw
