from __future__ import annotations

import json
from pathlib import Path

from scripts.refresh_scentai_jarvis_state import refresh_state


def test_emit_refresh_probe() -> None:
    master = json.loads(
        Path("examples/retail/data/scentai_jarvis_master_status.json").read_text(encoding="utf-8")
    )
    state = refresh_state(generated_at=master["generated_at"])
    payload = {
        "fingerprints": {
            key: value.get("source_fingerprint_sha256")
            for key, value in state.items()
            if isinstance(value, dict) and value.get("source_fingerprint_sha256")
        },
        "mapping_summary": state["mapping_queue"]["summary"],
        "rabanne_mapping_item": next(
            item
            for item in state["mapping_queue"]["items"]
            if item["product_id"] == "SC-RABANNE-1-MILLION-EDT-100"
        ),
    }
    raise AssertionError(\n        "DUFYND_REFRESH_PROBE=" + json.dumps(payload, ensure_ascii=False, sort_keys=True)\n    )
