from __future__ import annotations

import json
from pathlib import Path

from scripts.refresh_scentai_jarvis_state import refresh_state


def test_dump_expected_derived_state_fingerprints() -> None:
    master = json.loads(
        Path("examples/retail/data/scentai_jarvis_master_status.json").read_text(
            encoding="utf-8"
        )
    )
    rebuilt = refresh_state(generated_at=master["generated_at"])
    keys = (
        "image_queue",
        "mapping_queue",
        "operations",
        "release_pipeline",
        "release_status",
        "master_status",
    )
    fingerprints = {
        key: rebuilt[key].get("source_fingerprint_sha256")
        for key in keys
    }
    payload = json.dumps(fingerprints, sort_keys=True)
    raise AssertionError("DUFYND_EXPECTED_FINGERPRINTS=" + payload)
