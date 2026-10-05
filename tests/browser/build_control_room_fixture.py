"""Generate an isolated DTO fixture; never read the live database or credentials."""

from __future__ import annotations

import json
import runpy
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from retail.api.jarvis_dashboard import build_snapshot

sys.path.insert(0, str(Path(__file__).parents[2]))

ns = runpy.run_path(str(Path(__file__).parents[1] / "test_jarvis_dashboard.py"))
now = datetime.now(UTC)
delta = now - ns["NOW"]


def shift(value):
    if isinstance(value, dict):
        return {key: shift(item) for key, item in value.items()}
    if isinstance(value, list):
        return [shift(item) for item in value]
    if isinstance(value, str) and value.startswith("2026-"):
        try:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if stamp.tzinfo:
                return (stamp + delta).isoformat()
        except ValueError:
            pass
    return value


# Explicit isolated acceptance variants; these never enter a production response.
crew_ns = runpy.run_path(str(Path(__file__).parents[1] / "test_jarvis_crew.py"))
healthy = crew_ns["healthy_data"]()
warning = crew_ns["healthy_data"]()
warning["credentials"] = [{"provider": "gmail", "status": "healthy", "expires_at": ns["STAMP"]}]
warning["tasks"] = [
    {
        "task_id": "jarvis_purchase_freshness_watchlist_20261001",
        "domain": "commerce",
        "title": "Automatischer Händler-Freshness-Check",
        "status": "blocked",
        "blocked_reason": "deterministic_merchant_coverage_required",
        "updated_at": ns["STAMP"],
    },
    {
        "task_id": "jarvis_dior_hypnotic_image_rights_outreach_20261001",
        "domain": "commerce",
        "title": "Dior Bildrechte",
        "status": "waiting_external",
        "updated_at": ns["STAMP"],
    },
]
active = crew_ns["healthy_data"]()
active["tasks"] = [
    {
        "task_id": "qa-tech",
        "domain": "tech",
        "title": "Attribution Guard prüfen",
        "status": "working",
    },
    {
        "task_id": "qa-money",
        "domain": "analytics",
        "title": "Launch-Funnel auswerten",
        "status": "working",
    },
]
active["active_runs"] = [
    ns["run_row"](
        execution_id="qa-zoro",
        worker_id="tech-worker",
        task_id="qa-tech",
        handler_id="ci_pr_verifier",
    ),
    ns["run_row"](
        execution_id="qa-nami",
        worker_id="supervisor_v2",
        task_id="qa-money",
        handler_id="analytics_funnel_audit",
    ),
]
gate = crew_ns["healthy_data"]()
gate["tasks"] = [
    {
        "task_id": "qa-review",
        "domain": "content",
        "title": "Creative prüfen",
        "status": "waiting_human_input",
    }
]
critical = crew_ns["healthy_data"]()
critical["smoke"][0].update(status="failed", passed=17)
old = crew_ns["healthy_data"]()
old["smoke"][0]["observed_at"] = (ns["NOW"] - timedelta(hours=12)).isoformat()
output = build_snapshot(shift(warning), now=now)
output["_qa_scenarios"] = {
    name: build_snapshot(shift(data), now=now)
    for name, data in (
        ("healthy", healthy),
        ("warning", warning),
        ("active", active),
        ("gate", gate),
        ("critical", critical),
        ("old", old),
    )
}
Path(sys.argv[1]).write_text(json.dumps(output))
