from __future__ import annotations

import json

from scripts.refresh_scentai_jarvis_state import refresh_state


def test_debug_expected_dior_state_fingerprints() -> None:
    state = refresh_state(generated_at="2026-09-29T21:03:00+00:00")
    keys = ("operations", "release_status", "release_pipeline", "master_status")
    payload = {key: state[key].get("source_fingerprint_sha256") for key in keys}
    raise AssertionError("EXPECTED_DIOR_STATE=" + json.dumps(payload, sort_keys=True))
