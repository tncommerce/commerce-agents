"""Detect semantic drift between committed Jarvis snapshots and current source data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.refresh_scentai_jarvis_state import refresh_state

DATA_DIR = Path("examples/retail/data")

SNAPSHOTS = {
    "mapping_queue": DATA_DIR / "scentai_merchant_mapping_work_queue.json",
    "affiliate_status": DATA_DIR / "scentai_affiliate_activation_status.json",
    "image_queue": DATA_DIR / "scentai_image_approval_work_queue.json",
    "feed_queue": DATA_DIR / "scentai_release_01_feed_activation_queue.json",
    "release_status": DATA_DIR / "scentai_release_01_gate_status.json",
    "release_pipeline": DATA_DIR / "scentai_release_pipeline_status.json",
    "operations": DATA_DIR / "scentai_jarvis_operations_status.json",
    "content_status": DATA_DIR / "scentai_content_operations_status.json",
    "content_status_batch02": DATA_DIR / "scentai_content_operations_status_batch02.json",
    "content_status_batch03": DATA_DIR / "scentai_content_operations_status_batch03.json",
    "content_pipeline": DATA_DIR / "scentai_content_pipeline_status.json",
    "media_queue": DATA_DIR / "scentai_media_generation_queue.json",
    "master_status": DATA_DIR / "scentai_jarvis_master_status.json",
}

VOLATILE_KEYS = {"generated_at", "source_fingerprint_sha256"}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _semantic(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _semantic(item)
            for key, item in value.items()
            if key not in VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [_semantic(item) for item in value]
    return value


def test_committed_jarvis_snapshots_match_current_source_data() -> None:
    master = _load(SNAPSHOTS["master_status"])
    generated_at = str(master.get("generated_at") or "2026-09-26T16:55:00+00:00")
    rebuilt = refresh_state(generated_at=generated_at)

    assert set(SNAPSHOTS) <= set(rebuilt)

    drifted: list[str] = []
    for key, path in SNAPSHOTS.items():
        committed = _semantic(_load(path))
        current = _semantic(rebuilt[key])
        if committed != current:
            drifted.append(key)

    assert not drifted, "stale derived Jarvis snapshots: " + ", ".join(drifted)
