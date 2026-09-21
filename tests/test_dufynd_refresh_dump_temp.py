from __future__ import annotations

import base64
import json

from scripts.refresh_scentai_jarvis_state import refresh_state


def test_dump_refreshed_jarvis_state_for_branch_reconciliation() -> None:
    state = refresh_state(generated_at="2026-09-20T17:55:39+00:00")
    payload = {
        "feed_queue": state["feed_queue"],
        "operations": state["operations"],
        "master_status": state["master_status"],
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = base64.b64encode(raw).decode("ascii")
    raise AssertionError("DUFYND_REFRESH_DUMP=" + encoded)
