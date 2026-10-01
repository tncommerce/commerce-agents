from __future__ import annotations

import base64
import json
from pathlib import Path

from scripts.refresh_scentai_jarvis_state import refresh_state

DATA_DIR = Path("examples/retail/data")
OUTPUTS = {
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
PROTECTED = [
    "examples/retail/data/dufynd_notino_delina_black_opium_live_routing_20261001.json",
    "examples/retail/data/merchant_offers.json",
    "examples/retail/data/merchant_partners.json",
    "examples/retail/data/merchant_product_mappings.json",
    "examples/retail/data/scentai_affiliate_activation_review_notino_20260930.json",
    "examples/retail/data/scentai_affiliate_activation_status.json",
    "examples/retail/data/scentai_affiliate_program_events.json",
    "examples/retail/data/scentai_affiliate_programs.json",
    "examples/retail/data/scentai_affiliate_tracking_preflight_notino_20260930.json",
    "tests/test_dufynd_merchant_offer_integrity.py"
]


def test_export_deterministic_jarvis_snapshot_delta_for_pr589() -> None:
    master = json.loads((DATA_DIR / "scentai_jarvis_master_status.json").read_text(encoding="utf-8"))
    generated_at = str(master["generated_at"])
    rebuilt = refresh_state(generated_at=generated_at)

    changed: dict[str, str] = {}
    for key, path in OUTPUTS.items():
        rendered = json.dumps(rebuilt[key], ensure_ascii=False, indent=2) + "\n"
        committed = path.read_text(encoding="utf-8-sig")
        if committed != rendered:
            changed[path.as_posix()] = rendered

    protected_overlap = sorted(set(changed).intersection(PROTECTED))
    assert not protected_overlap, f"refresh would touch protected #589 files: {protected_overlap}"

    encoded = base64.b64encode(
        json.dumps(changed, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    print("DUFYND_SNAPSHOT_BUNDLE_B64=" + encoded)
    print("DUFYND_SNAPSHOT_CHANGED_PATHS=" + json.dumps(sorted(changed), separators=(",", ":")))
    raise AssertionError("diagnostic export only")
