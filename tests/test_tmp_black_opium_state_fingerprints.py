from __future__ import annotations

import json
from pathlib import Path

from scripts.refresh_scentai_jarvis_state import refresh_state

MASTER = Path("examples/retail/data/scentai_jarvis_master_status.json")


def test_tmp_print_black_opium_state_fingerprints() -> None:
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    state = refresh_state(generated_at=master["generated_at"])
    fingerprints = {
        key: state[key]["source_fingerprint_sha256"]
        for key in ("release_status", "release_pipeline", "operations", "master_status")
    }
    raise AssertionError(json.dumps(fingerprints, sort_keys=True))
