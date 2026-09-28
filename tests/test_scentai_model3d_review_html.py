from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from scripts.render_scentai_model3d_review_html import render_html, review_candidates

MODEL_URL = "/products/models/test-fragrance-100ml.glb"


def minimal_glb() -> bytes:
    payload = bytearray(b"glTF")
    payload.extend((2).to_bytes(4, "little"))
    payload.extend((12).to_bytes(4, "little"))
    return bytes(payload)


def payload(sha256: str) -> dict:
    return {
        "version": 1,
        "status": "review_only_not_live",
        "candidates": [
            {
                "product_id": "SC-TEST-100",
                "brand": "Test Brand",
                "name": "<Test Fragrance>",
                "concentration": "Eau de Parfum",
                "volume_ml": 100,
                "variant": "100ml",
                "role": "model_3d",
                "model_url": MODEL_URL,
                "model_sha256": sha256,
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


def public_root(tmp_path: Path) -> Path:
    root = tmp_path / "public"
    model = root / "products" / "models" / "test-fragrance-100ml.glb"
    model.parent.mkdir(parents=True)
    model.write_bytes(minimal_glb())
    return root


def test_review_packet_verifies_current_glb_bytes_and_stays_pending(tmp_path: Path) -> None:
    root = public_root(tmp_path)
    sha256 = hashlib.sha256(minimal_glb()).hexdigest()

    rows = review_candidates(payload(sha256), root)

    assert len(rows) == 1
    assert rows[0]["review_status"] == "pending_review"
    assert rows[0]["geometry_review_required"] is True
    assert rows[0]["verified_model_sha256"] == sha256


def test_review_packet_rejects_changed_model_bytes(tmp_path: Path) -> None:
    root = public_root(tmp_path)

    with pytest.raises(ValueError, match="model_asset_hash_mismatch"):
        review_candidates(payload("0" * 64), root)


@pytest.mark.parametrize(
    ("field", "error"),
    [
        ("commercial_use_allowed", "model_commercial_use_not_allowed"),
        ("public_distribution_allowed", "model_public_distribution_not_allowed"),
        ("interactive_web_display_allowed", "model_interactive_web_display_not_allowed"),
    ],
)
def test_review_packet_requires_explicit_rights(tmp_path: Path, field: str, error: str) -> None:
    root = public_root(tmp_path)
    sha256 = hashlib.sha256(minimal_glb()).hexdigest()
    data = payload(sha256)
    data["candidates"][0]["rights_evidence"][field] = False

    with pytest.raises(ValueError, match=error):
        review_candidates(data, root)


def test_rendered_html_is_review_only_interactive_and_escapes_product_text(tmp_path: Path) -> None:
    root = public_root(tmp_path)
    sha256 = hashlib.sha256(minimal_glb()).hexdigest()

    rendered = render_html(review_candidates(payload(sha256), root))

    assert "<model-viewer" in rendered
    assert 'src="/products/models/test-fragrance-100ml.glb"' in rendered
    assert "&lt;Test Fragrance&gt;" in rendered
    assert "NOT LIVE · PENDING REVIEW" in rendered
    assert "HUMAN REVIEW REQUIRED" in rendered
    assert "kann kein Modell freigeben" in rendered
    assert "<button" not in rendered
    assert "<form" not in rendered


def test_empty_review_queue_renders_safe_empty_state(tmp_path: Path) -> None:
    rows = review_candidates(
        {"version": 1, "status": "review_only_not_live", "candidates": []},
        tmp_path,
    )

    rendered = render_html(rows)

    assert "Keine 3D-Kandidaten in Prüfung" in rendered
    assert "<model-viewer" not in rendered
