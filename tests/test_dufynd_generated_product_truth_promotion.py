from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from scripts.promote_dufynd_generated_product_truth import (
    GENERATED_PRODUCT_TRUTH_STATUS,
    apply_staged_registration,
    copy_public_asset,
    promotion_plan,
)

DATA = Path("examples/retail/data")
QUEUE = DATA / "dufynd_product_visual_review_queue.json"
STAGED_CANDIDATES = DATA / "dufynd_staged_image_fidelity_candidates_20260930.json"
LIVE_CATALOG = DATA / "scentai_products.json"
STAGING_CATALOG = DATA / "scentai_catalog_staging.json"

CREED_ID = "SC-CREED-ABSOLU-AVENTUS-100"
LIBRE_ID = "SC-YSL-LIBRE-EDP-90"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _payloads() -> tuple[dict, dict, dict, dict]:
    return (
        _load(QUEUE),
        _load(STAGED_CANDIDATES),
        _load(LIVE_CATALOG),
        _load(STAGING_CATALOG),
    )


def _staged_row(payload: dict, product_id: str) -> dict:
    return next(
        row for row in payload["products"] if row["product_id"] == product_id
    )


def _candidate_row(payload: dict, product_id: str) -> dict:
    return next(
        row for row in payload["items"] if row["product_id"] == product_id
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_current_creed_and_libre_structural_dry_runs_are_fail_closed(
    tmp_path: Path,
) -> None:
    queue, staged_candidates, live_catalog, staging_catalog = _payloads()

    creed = promotion_plan(
        queue,
        staged_candidates,
        live_catalog,
        staging_catalog,
        product_id=CREED_ID,
        public_asset="/products/creed-absolu-aventus-100-generated.png",
        public_root=tmp_path / "creed-public",
    )
    assert creed["candidate_source"] == "visual_review_queue"
    assert creed["catalog_scope"] == "live"
    assert creed["variant"] == "100ml"
    assert creed["provenance"] == "dufynd_generated"
    assert creed["fidelity_status"] == "verified"
    assert creed["write_supported"] is False
    assert creed["catalog_promotion"] is False
    assert creed["public_activation"] is False
    assert creed["catalog_ready_will_change"] is False
    assert creed["next_gate"] == "separate_live_catalog_product_truth_activation_required"

    libre = promotion_plan(
        queue,
        staged_candidates,
        live_catalog,
        staging_catalog,
        product_id=LIBRE_ID,
        public_asset="/products/ysl-libre-edp-90-generated.png",
        public_root=tmp_path / "libre-public",
    )
    assert libre["candidate_source"] == "staged_fidelity"
    assert libre["catalog_scope"] == "staging"
    assert libre["variant"] == "90ml"
    assert libre["generated_media_status"] == GENERATED_PRODUCT_TRUTH_STATUS
    assert libre["write_supported"] is True
    assert libre["catalog_promotion"] is False
    assert libre["public_activation"] is False
    assert libre["catalog_ready_will_change"] is False
    assert libre["next_gate"] == "normal_catalog_promotion_after_all_remaining_gates"


def test_staged_write_path_requires_explicit_human_fidelity_approval(
    tmp_path: Path,
) -> None:
    queue, staged_candidates, live_catalog, staging_catalog = _payloads()
    libre = _candidate_row(staged_candidates, LIBRE_ID)
    libre["status"] = "pending_human_fidelity"

    with pytest.raises(
        ValueError,
        match="staged_candidate_not_human_fidelity_approved",
    ):
        promotion_plan(
            queue,
            staged_candidates,
            live_catalog,
            staging_catalog,
            product_id=LIBRE_ID,
            public_asset="/products/ysl-libre-edp-90-generated.png",
            public_root=tmp_path,
        )

    libre["status"] = "human_fidelity_approved_pending_registration"
    libre["approval_basis"] = ""
    with pytest.raises(
        ValueError,
        match="explicit_human_fidelity_approval_required",
    ):
        promotion_plan(
            queue,
            staged_candidates,
            live_catalog,
            staging_catalog,
            product_id=LIBRE_ID,
            public_asset="/products/ysl-libre-edp-90-generated.png",
            public_root=tmp_path,
        )


def test_generated_candidate_must_match_exact_canonical_variant(
    tmp_path: Path,
) -> None:
    queue, staged_candidates, live_catalog, staging_catalog = _payloads()
    _staged_row(staging_catalog, LIBRE_ID)["volume_ml"] = 100

    with pytest.raises(
        ValueError,
        match="candidate_volume_does_not_match_canonical_product",
    ):
        promotion_plan(
            queue,
            staged_candidates,
            live_catalog,
            staging_catalog,
            product_id=LIBRE_ID,
            public_asset="/products/ysl-libre-edp-90-generated.png",
            public_root=tmp_path,
        )


def test_generated_candidate_bytes_and_public_target_are_verified(
    tmp_path: Path,
) -> None:
    queue, staged_candidates, live_catalog, staging_catalog = _payloads()
    libre = _candidate_row(staged_candidates, LIBRE_ID)
    libre["sha256"] = "0" * 64

    with pytest.raises(ValueError, match="candidate_sha256_mismatch"):
        promotion_plan(
            queue,
            staged_candidates,
            live_catalog,
            staging_catalog,
            product_id=LIBRE_ID,
            public_asset="/products/ysl-libre-edp-90-generated.png",
            public_root=tmp_path,
        )

    queue, staged_candidates, live_catalog, staging_catalog = _payloads()
    with pytest.raises(ValueError, match="public_asset_must_be_safe_products_path"):
        promotion_plan(
            queue,
            staged_candidates,
            live_catalog,
            staging_catalog,
            product_id=LIBRE_ID,
            public_asset="/products/../ysl-libre.png",
            public_root=tmp_path,
        )

    with pytest.raises(
        ValueError,
        match="public_asset_extension_must_match_candidate",
    ):
        promotion_plan(
            queue,
            staged_candidates,
            live_catalog,
            staging_catalog,
            product_id=LIBRE_ID,
            public_asset="/products/ysl-libre-edp-90-generated.webp",
            public_root=tmp_path,
        )


def test_staged_registration_preserves_separate_catalog_activation_gate(
    tmp_path: Path,
) -> None:
    queue, staged_candidates, live_catalog, staging_catalog = _payloads()
    live_before = copy.deepcopy(live_catalog)
    queue_before = copy.deepcopy(queue)
    public_root = tmp_path / "public"

    plan = promotion_plan(
        queue,
        staged_candidates,
        live_catalog,
        staging_catalog,
        product_id=LIBRE_ID,
        public_asset="/products/ysl-libre-edp-90-generated.png",
        public_root=public_root,
    )
    apply_staged_registration(
        staging_catalog,
        staged_candidates,
        plan,
        registered_at="2026-10-01T20:00:00+00:00",
    )
    copy_public_asset(plan, public_root=public_root)

    staged = _staged_row(staging_catalog, LIBRE_ID)
    assert staged["media"]["image_url"] == plan["public_asset"]
    assert staged["media"]["image_status"] == GENERATED_PRODUCT_TRUTH_STATUS
    assert staged["media"]["image_source_class"] == "dufynd_generated"
    assert staged["media"]["image_source_sha256"] == plan["source_sha256"]
    assert staged["media"]["image_fidelity_approval_basis"] == plan["approval_basis"]
    assert staged["media"]["image_exact_variant_verified"] is True
    assert staged["media"]["image_variant"] == "90ml"
    assert staged["validation"]["catalog_ready"] is False
    assert "approved_product_image_pending" not in staged["validation"]["blockers"]

    candidate = _candidate_row(staged_candidates, LIBRE_ID)
    assert candidate["status"] == "human_fidelity_approved_registered_product_truth"
    assert candidate["source_registration_status"] == "registered_product_truth"
    assert candidate["catalog_promotion"] is False
    assert candidate["public_activation"] is False
    assert candidate["registered_public_asset"] == plan["public_asset"]

    copied = public_root / plan["public_asset"].removeprefix("/")
    source = Path(plan["source_candidate_asset"])
    assert copied.is_file()
    assert _sha256(copied) == _sha256(source)
    assert live_catalog == live_before
    assert queue == queue_before


def test_live_creed_write_path_requires_separate_activation_gate(
    tmp_path: Path,
) -> None:
    queue, staged_candidates, live_catalog, staging_catalog = _payloads()
    plan = promotion_plan(
        queue,
        staged_candidates,
        live_catalog,
        staging_catalog,
        product_id=CREED_ID,
        public_asset="/products/creed-absolu-aventus-100-generated.png",
        public_root=tmp_path,
    )

    with pytest.raises(
        ValueError,
        match="live_catalog_product_requires_separate_activation_gate",
    ):
        apply_staged_registration(
            staging_catalog,
            staged_candidates,
            plan,
            registered_at="2026-10-01T20:00:00+00:00",
        )
