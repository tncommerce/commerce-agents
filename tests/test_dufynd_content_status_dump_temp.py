from __future__ import annotations

import base64
import json

from scripts.refresh_scentai_jarvis_state import refresh_state


def test_dump_content_status_sync() -> None:
    state = refresh_state(generated_at="2026-09-21T21:06:48+00:00")
    payload = {
        "content_pipeline": state["content_pipeline"],
        "master_status": state["master_status"],
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = base64.b64encode(raw).decode("ascii")
    raise AssertionError("DUFYND_CONTENT_STATUS_DUMP=" + encoded)
