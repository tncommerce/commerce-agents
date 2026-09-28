from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.build_scentai_model3d_review_bundle import build_review_bundle

MODEL_URL = "/products/models/test-fragrance-100ml.glb"


def minimal_glb() -> bytes:
    payload = bytearray(b"glTF")
    payload.extend((2).to_bytes(4, "little"))
    payload.extend((12).to_bytes(4, "little"))
    return bytes(payload)


def candidate_payload(model_sha256: str) -> dict:
    return {
        "version": 1,
        "status": "review_only_not_live",
        "updated_at": "2026-09-28T17:00:00+00:00",
        "candidates": [
            {
                "product_id": "SC-TEST-100",
                "brand": "Test Brand",
                "name": "Test Fragrance",
                "concentration": "Eau de Parfum",
                "volume_ml": 100,
                "variant": "100ml",
                "role": "model_3d",
                "model_url": MODEL_URL,
                "model_sha256": model_sha256,
                "review_status": "pending_review",
                "geometry_review_required": True,
                "proposed_fidelity_status": "verified",
                "source_class": "written_manufacturer_3d_permission",
                "exact_variant_verified": True,
                "rights_evidence": {
                    "rights_basis_id": "manufacturer-model-rights-001",
                    "rights_status": "verified_for_publisher_service",
                    "rights_checked_at": "2026-09-28",
                    "commercial_use_allowed": True,
                    "public_distribution_allowed": True,
                    "interactive_web_display_allowed": True,
                },
            }
        ],
    }


def test_review_bundle_is_portable_and_review_only(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    model_path = public_root / "products" / "models" / "test-fragrance-100ml.glb"
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(minimal_glb())
    sha256 = hashlib.sha256(minimal_glb()).hexdigest()

    output = tmp_path / "review"
    manifest = build_review_bundle(
        candidate_payload(sha256),
        public_root=public_root,
        output_dir=output,
    )

    assert manifest["status"] == "review_only_not_live"
    assert manifest["candidate_count"] == 1
    assert manifest["candidates"][0]["review_status"] == "pending_review"

    rendered = (output / "index.html").read_text(encoding="utf-8")
    assert 'src="products/models/test-fragrance-100ml.glb"' in rendered
    assert 'src="/products/models/test-fragrance-100ml.glb"' not in rendered
    assert "HUMAN REVIEW REQUIRED" in rendered
    assert "kann kein Modell freigeben" in rendered

    copied = output / "products" / "models" / "test-fragrance-100ml.glb"
    assert copied.read_bytes() == minimal_glb()

    persisted = json.loads((output / "review-candidates.json").read_text(encoding="utf-8"))
    assert persisted["candidate_count"] == 1
    assert persisted["candidates"][0]["verified_model_sha256"] == sha256
    assert "Final geometry and visual approval remains human-only." in (
        output / "README.txt"
    ).read_text(encoding="utf-8")


def test_empty_review_bundle_still_produces_safe_artifact(tmp_path: Path) -> None:
    output = tmp_path / "review"
    manifest = build_review_bundle(
        {"version": 1, "status": "review_only_not_live", "candidates": []},
        public_root=tmp_path / "public",
        output_dir=output,
    )

    assert manifest["candidate_count"] == 0
    assert "Keine 3D-Kandidaten in Prüfung" in (output / "index.html").read_text(encoding="utf-8")
