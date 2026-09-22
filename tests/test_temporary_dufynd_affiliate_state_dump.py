from __future__ import annotations

import base64
import json
import zlib

from scripts.refresh_scentai_jarvis_state import refresh_state

GENERATED_AT = "2026-09-21T21:18:43+00:00"
DUMP_KEYS = (
    "affiliate_status",
    "release_status",
    "release_pipeline",
    "operations",
    "master_status",
)


def test_dump_reconciled_jarvis_state() -> None:
    state = refresh_state(generated_at=GENERATED_AT)
    for key in DUMP_KEYS:
        raw = (json.dumps(state[key], ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        payload = base64.b64encode(zlib.compress(raw, level=9)).decode("ascii")
        print(f"DUFYND_STATE_DUMP::{key}::{payload}")

    raise AssertionError("temporary derived-state dump")
