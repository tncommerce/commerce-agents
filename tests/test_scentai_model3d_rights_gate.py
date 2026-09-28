from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from scripts.approve_scentai_model3d import apply_approval, approval_plan
from scripts.register_scentai_model3d import apply_registration, registration_plan
from scripts.scentai_model3d_guard import (
    normalize_model_url,
    validate_glb_bytes,
    validated_model_sha256,
)

PRODUCT_ID = "SC-TEST-100"
MODEL_URL = "/products/models/test-fragrance-100ml.glb"


def minimal_glb() -> bytes:
    payload = bytearray(b"glTF")
    payload.extend((2).to_bytes(4, "little"))
    payload.extend((12).to_bytes(4, "little"))
    return bytes(payload)


def products_payload(*, existing_visuals=None) -> dict:
    return {
        "products": [
            {
                "product_id": PRODUCT_ID,
                "brand": "Test Brand",
                "name": "Test Fragrance",
                "concentration": "Eau de Parfum",
                "volume_ml": 100,
                "visuals": list(existing_visuals or []),
            }
        ]
    }


def candidates_payload() -> dict:
    return {
        "version": 1,
        "status": "review_only_not_live",
        "updated_at": None,
        "candidates": [],
    }


def registration_for(payload=None, **overrides) -> dict:
    values = {
        "product_id": PRODUCT_ID,
        "model_url": MODEL_URL,
        "model_sha256": hashlib.sha256(minimal_glb()).hexdigest(),
        "source_class": "written_manufacturer_3d_permission",
        "rights_basis_id": "manufacturer-model-rights-001",
        "rights_checked_at": "2026-09-28",
        "exact_variant_verified": True,
        "commercial_use_allowed": True,
        "public_distribution_allowed": True,
        "interactive_web_display_allowed": True,
        "evidence_note": "Exact 100 ml geometry and label placement verified.",
    }
    values.update(overrides)
    return registration_plan(
        products_payload(),
        payload or candidates_payload(),
        **values,
    )


def registered_candidates() -> dict:
    payload = candidates_payload()
    plan = registration_for(payload=payload)
    apply_registration(
        payload,
        plan,
        registered_at="2026-09-28T16:00:00+00:00",
    )
    return payload


def test_glb_guard_accepts_local_version_2_asset_and_hashes_bytes(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    model_path = public_root / "products" / "models" / "test.glb"
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(minimal_glb())

    assert normalize_model_url("/products/models/test.glb") == "/products/models/test.glb"
    assert validated_model_sha256(public_root, "/products/models/test.glb") == (
        hashlib.sha256(minimal_glb()).hexdigest()
    )


@pytest.mark.parametrize(
    "model_url",
    [
        "https://cdn.example.com/model.glb",
        "//cdn.example.com/model.glb",
        "/products/test.glb",
        "/products/models/test.gltf",
        "/products/models/test.glb?token=SECRET",
        "/products/models/test.glb#fragment",
        "/products/models/%2e%2e/secret.glb",
    ],
)
def test_glb_guard_rejects_nonlocal_or_ambiguous_targets(model_url: str) -> None:
    with pytest.raises(ValueError, match="model_url_must_be_local_products_model_glb"):
        normalize_model_url(model_url)


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        (b"", "glb_header_truncated"),
        (b"BAD!" + (2).to_bytes(4, "little") + (12).to_bytes(4, "little"), "glb_magic_invalid"),
        (b"glTF" + (1).to_bytes(4, "little") + (12).to_bytes(4, "little"), "glb_version_unsupported"),
        (b"glTF" + (2).to_bytes(4, "little") + (99).to_bytes(4, "little"), "glb_declared_length_mismatch"),
    ],
)
def test_glb_guard_rejects_invalid_container(payload: bytes, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        validate_glb_bytes(payload)


def test_registration_is_review_only_and_variant_bound() -> None:
    plan = registration_for()
    candidate = plan["candidate"]

    assert candidate["review_status"] == "pending_review"
    assert candidate["geometry_review_required"] is True
    assert candidate["role"] == "model_3d"
    assert candidate["proposed_fidelity_status"] == "verified"
    assert candidate["variant"] == "100ml"
    assert candidate["exact_variant_verified"] is True
    assert candidate["rights_evidence"]["rights_status"] == "verified_for_publisher_service"
    assert candidate["rights_evidence"]["interactive_web_display_allowed"] is True


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("exact_variant_verified", False, "model_exact_variant_not_verified"),
        ("commercial_use_allowed", False, "model_commercial_use_not_allowed"),
        ("public_distribution_allowed", False, "model_public_distribution_not_allowed"),
        ("interactive_web_display_allowed", False, "model_interactive_web_display_not_allowed"),
    ],
)
def test_registration_requires_exact_variant_and_explicit_rights(
    field: str,
    value: object,
    error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        registration_for(**{field: value})


def test_licensed_3d_asset_requires_license_metadata() -> None:
    with pytest.raises(ValueError, match="model_license_metadata_incomplete"):
        registration_for(source_class="licensed_3d_asset")

    plan = registration_for(
        source_class="licensed_3d_asset",
        license_name="Commercial 3D asset licence",
        license_url="https://assets.example.com/license",
        attribution_text="Asset creator",
    )
    assert plan["candidate"]["rights_evidence"]["license_name"] == (
        "Commercial 3D asset licence"
    )


def test_registration_never_auto_approves() -> None:
    payload = candidates_payload()
    plan = registration_for(payload=payload)
    apply_registration(payload, plan, registered_at="2026-09-28T16:00:00+00:00")

    assert payload["status"] == "review_only_not_live"
    assert payload["candidates"][0]["review_status"] == "pending_review"


def test_approval_requires_explicit_human_geometry_review() -> None:
    candidates = registered_candidates()
    sha256 = candidates["candidates"][0]["model_sha256"]

    with pytest.raises(ValueError, match="human_3d_geometry_approval_required"):
        approval_plan(
            products_payload(),
            candidates,
            product_id=PRODUCT_ID,
            model_url=MODEL_URL,
            actual_model_sha256=sha256,
            human_visual_approval=False,
        )


def test_approval_rejects_changed_model_bytes() -> None:
    candidates = registered_candidates()

    with pytest.raises(ValueError, match="model_asset_hash_mismatch"):
        approval_plan(
            products_payload(),
            candidates,
            product_id=PRODUCT_ID,
            model_url=MODEL_URL,
            actual_model_sha256="0" * 64,
            human_visual_approval=True,
        )


def test_human_approved_model_activates_as_verified_structured_visual() -> None:
    products = products_payload(
        existing_visuals=[
            {
                "role": "cutout",
                "url": "/products/test.webp",
                "provenance": "test",
                "fidelity_status": "verified",
                "variant": "100ml",
            }
        ]
    )
    candidates = registered_candidates()
    sha256 = candidates["candidates"][0]["model_sha256"]

    plan = approval_plan(
        products,
        candidates,
        product_id=PRODUCT_ID,
        model_url=MODEL_URL,
        actual_model_sha256=sha256,
        human_visual_approval=True,
    )
    apply_approval(
        products,
        candidates,
        plan,
        reviewed_at="2026-09-28T17:00:00+00:00",
    )

    model = next(
        visual
        for visual in products["products"][0]["visuals"]
        if visual["role"] == "model_3d"
    )
    assert model["url"] == MODEL_URL
    assert model["fidelity_status"] == "verified"
    assert model["variant"] == "100ml"
    assert model["model_sha256"] == sha256
    assert model["rights_basis_id"] == "manufacturer-model-rights-001"

    candidate = candidates["candidates"][0]
    assert candidate["review_status"] == "approved"
    assert candidate["geometry_review_required"] is False
    assert candidate["approved_model_sha256"] == sha256


def test_existing_verified_model_requires_explicit_replace() -> None:
    candidates = registered_candidates()
    sha256 = candidates["candidates"][0]["model_sha256"]
    products = products_payload(
        existing_visuals=[
            {
                "role": "model_3d",
                "url": "/products/models/current.glb",
                "provenance": "licensed_3d_asset",
                "fidelity_status": "verified",
                "variant": "100ml",
                "model_sha256": "1" * 64,
            }
        ]
    )

    with pytest.raises(ValueError, match="verified_model_already_exists_use_replace_flag"):
        approval_plan(
            products,
            candidates,
            product_id=PRODUCT_ID,
            model_url=MODEL_URL,
            actual_model_sha256=sha256,
            human_visual_approval=True,
        )


def test_committed_candidate_queue_starts_review_only_and_empty() -> None:
    queue = json.loads(
        Path("examples/retail/data/dufynd_model3d_candidates.json").read_text(
            encoding="utf-8"
        )
    )
    assert queue["status"] == "review_only_not_live"
    assert queue["candidates"] == []
