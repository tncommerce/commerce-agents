"""Generate an isolated DTO fixture; never read the live database or credentials."""

from __future__ import annotations

import json
import runpy
import sys
from datetime import UTC, datetime
from pathlib import Path

from retail.api.jarvis_dashboard import build_snapshot

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


Path(sys.argv[1]).write_text(json.dumps(build_snapshot(shift(ns["ceo_data"]()), now=now)))
