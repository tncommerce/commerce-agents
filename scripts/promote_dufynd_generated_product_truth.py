from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path("examples/retail/data")
DEFAULT_QUEUE = DATA_DIR / "dufynd_product_visual_review_queue.json"
DEFAULT_STAGED_CANDIDATES = DATA_DIR / "dufynd_staged_image_fidelity_candidates_20260930.json"
DEFAULT_LIVE_CATALOG = DATA_DIR / "scentai_products.json"
DEFAULT_STAGING_CATALOG = DATA_DIR / "scentai_catalog_staging.json"
DEFAULT_PUBLIC_ROOT = Path("examples/retail/storefront-web/public")

GENERATED_PRODUCT_TRUTH_STATUS = "verified_dufynd_generated_product_truth"
QUEUE_APPROVED_STATUS = "human_fidelity_approved_pending_promotion"
STAGED_APPROVED_STATUS = "human_fidelity_approved_pending_registration"
EXPLICIT_APPROVAL_PREFIX = "explicit_user_visual_approval_"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _positive_int(value: Any, *, error: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(error) from exc
    if parsed <= 0:
        raise ValueError(error)
    return parsed


def _explicit_approval_basis(value: Any) -> str:
    basis = str(value or "").strip()
    if not basis.startswith(EXPLICIT_APPROVAL_PREFIX):
        raise ValueError("explicit_human_fidelity_approval_required")
    return basis


def _safe_candidate_asset(
    candidate_asset: Any,
    *,
    repo_root: Path,
    expected_sha256: Any,
) -> Path:
    relative = str(candidate_asset or "").strip()
    if not relative:
        raise ValueError("candidate_asset_required")
    if "\\" in relative:
        raise ValueError("candidate_asset_must_stay_in_review_assets")

    root = (repo_root / "examples/retail/review-assets").resolve()
    path = (repo_root / relative).resolve()
    if root != path and root not in path.parents:
        raise ValueError("candidate_asset_must_stay_in_review_assets")
    if not path.is_file() or path.is_symlink():
        raise ValueError("candidate_asset_missing_or_unsafe")

    expected = str(expected_sha256 or "").strip().lower()
    if len(expected) != 64:
        raise ValueError("candidate_sha256_required")
    if _sha256(path) != expected:
        raise ValueError("candidate_sha256_mismatch")
    return path


def _safe_public_asset(
    public_asset: Any,
    *,
    public_root: Path,
    source_path: Path,
) -> Path:
    value = str(public_asset or "").strip()
    if (
        not value.startswith("/products/")
        or value.startswith("//")
        or "\\" in value
        or "?" in value
        or "#" in value
    ):
        raise ValueError("public_asset_must_be_safe_products_path")

    relative = Path(value.removeprefix("/"))
    if ".." in relative.parts:
        raise ValueError("public_asset_must_be_safe_products_path")
    target = (public_root / relative).resolve()
    root = public_root.resolve()
    if root != target and root not in target.parents:
        raise ValueError("public_asset_must_be_safe_products_path")
    if target.suffix.lower() != source_path.suffix.lower():
        raise ValueError("public_asset_extension_must_match_candidate")

    if target.exists():
        if not target.is_file() or target.is_symlink():
            raise ValueError("public_asset_target_unsafe")
        if _sha256(target) != _sha256(source_path):
            raise ValueError("public_asset_conflict")
    return target


def _find_product(payload: dict[str, Any], product_id: str) -> dict[str, Any] | None:
    return next(
        (
            row
            for row in payload.get("products", [])
            if str(row.get("product_id") or "").strip() == product_id
        ),
        None,
    )


def _normalized_queue_candidate(row: dict[str, Any]) -> dict[str, Any]:
    if str(row.get("status") or "").strip() != QUEUE_APPROVED_STATUS:
        raise ValueError("queue_candidate_not_human_fidelity_approved")

    provenance = row.get("candidate_provenance") or {}
    if str(provenance.get("source") or "").strip() != "dufynd_generated":
        raise ValueError("candidate_provenance_not_dufynd_generated")
    if str(provenance.get("approval_status") or "").strip() != "human_fidelity_approved":
        raise ValueError("candidate_provenance_not_human_approved")
    if provenance.get("public_activation") is not False:
        raise ValueError("candidate_public_activation_must_be_false")

    reference = row.get("reference_variant") or {}
    if reference.get("reference_only") is not True:
        raise ValueError("candidate_reference_must_be_reference_only")

    return {
        "candidate_source": "visual_review_queue",
        "product_id": str(row.get("product_id") or "").strip(),
        "priority": str(row.get("priority") or "").strip() or None,
        "candidate_asset": str(row.get("candidate_asset") or "").strip(),
        "sha256": str(provenance.get("sha256") or "").strip(),
        "generator": str(provenance.get("generator") or "").strip(),
        "width": _positive_int(provenance.get("width"), error="candidate_width_required"),
        "height": _positive_int(provenance.get("height"), error="candidate_height_required"),
        "has_alpha": provenance.get("has_alpha"),
        "approval_basis": _explicit_approval_basis(row.get("approval_basis")),
        "approved_at": str(row.get("approved_at") or "").strip(),
        "volume_ml": _positive_int(
            reference.get("volume_ml"),
            error="candidate_volume_required",
        ),
        "concentration": str(reference.get("concentration") or "").strip(),
        "evidence_url": str(row.get("evidence_url") or "").strip(),
    }


def _normalized_staged_candidate(row: dict[str, Any]) -> dict[str, Any]:
    if str(row.get("status") or "").strip() != STAGED_APPROVED_STATUS:
        raise ValueError("staged_candidate_not_human_fidelity_approved")
    if str(row.get("provenance") or "").strip() != "dufynd_generated_internal_candidate":
        raise ValueError("candidate_provenance_not_dufynd_generated")
    if str(row.get("source_registration_status") or "").strip() != "not_registered":
        raise ValueError("candidate_source_already_registered")
    if row.get("catalog_promotion") is not False:
        raise ValueError("candidate_catalog_promotion_must_be_false")
    if row.get("public_activation") is not False:
        raise ValueError("candidate_public_activation_must_be_false")
    if row.get("reference_only") is not True:
        raise ValueError("candidate_reference_must_be_reference_only")

    return {
        "candidate_source": "staged_fidelity",
        "product_id": str(row.get("product_id") or "").strip(),
        "priority": None,
        "candidate_asset": str(row.get("candidate_asset") or "").strip(),
        "sha256": str(row.get("sha256") or "").strip(),
        "generator": str(row.get("generator") or "").strip(),
        "width": _positive_int(row.get("width"), error="candidate_width_required"),
        "height": _positive_int(row.get("height"), error="candidate_height_required"),
        "has_alpha": row.get("has_alpha"),
        "approval_basis": _explicit_approval_basis(row.get("approval_basis")),
        "approved_at": str(row.get("approved_at") or "").strip(),
        "volume_ml": _positive_int(row.get("volume_ml"), error="candidate_volume_required"),
        "concentration": str(row.get("concentration") or "").strip(),
        "evidence_url": str(row.get("reference_url") or "").strip(),
    }


def _candidate(
    queue: dict[str, Any],
    staged_candidates: dict[str, Any],
    *,
    product_id: str,
    source: str = "auto",
) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []

    if source in {"auto", "visual_review_queue"}:
        row = next(
            (
                item
                for item in queue.get("items", [])
                if str(item.get("product_id") or "").strip() == product_id
            ),
            None,
        )
        if row is not None:
            matches.append(_normalized_queue_candidate(row))

    if source in {"auto", "staged_fidelity"}:
        row = next(
            (
                item
                for item in staged_candidates.get("items", [])
                if str(item.get("product_id") or "").strip() == product_id
            ),
            None,
        )
        if row is not None:
            matches.append(_normalized_staged_candidate(row))

    if not matches:
        raise ValueError("human_approved_generated_candidate_not_found")
    if len(matches) != 1:
        raise ValueError("candidate_source_ambiguous")
    return matches[0]


def _catalog_context(
    live_catalog: dict[str, Any],
    staging_catalog: dict[str, Any],
    *,
    product_id: str,
) -> tuple[str, dict[str, Any]]:
    live = _find_product(live_catalog, product_id)
    staged = _find_product(staging_catalog, product_id)

    if live is None and staged is None:
        raise ValueError("canonical_product_not_found")
    if live is not None and staged is not None:
        live_volume = _positive_int(live.get("volume_ml"), error="canonical_volume_required")
        staged_volume = _positive_int(
            staged.get("volume_ml"),
            error="canonical_volume_required",
        )
        if live_volume != staged_volume:
            raise ValueError("live_and_staging_variant_conflict")
        return "live", live
    if live is not None:
        return "live", live
    assert staged is not None
    return "staging", staged


def _verified_truth_visual_exists(product: dict[str, Any]) -> bool:
    return any(
        str(visual.get("role") or "").strip() in {"primary", "cutout"}
        and str(visual.get("fidelity_status") or "").strip() == "verified"
        for visual in product.get("visuals", [])
    )


def promotion_plan(
    queue: dict[str, Any],
    staged_candidates: dict[str, Any],
    live_catalog: dict[str, Any],
    staging_catalog: dict[str, Any],
    *,
    product_id: str,
    public_asset: str,
    source: str = "auto",
    repo_root: Path = REPO_ROOT,
    public_root: Path = DEFAULT_PUBLIC_ROOT,
) -> dict[str, Any]:
    product_id = product_id.strip()
    if not product_id:
        raise ValueError("product_id_required")
    if source not in {"auto", "visual_review_queue", "staged_fidelity"}:
        raise ValueError("candidate_source_invalid")

    candidate = _candidate(
        queue,
        staged_candidates,
        product_id=product_id,
        source=source,
    )
    if candidate["product_id"] != product_id:
        raise ValueError("candidate_product_id_mismatch")
    if not candidate["approved_at"]:
        raise ValueError("candidate_approved_at_required")
    if not candidate["generator"]:
        raise ValueError("candidate_generator_required")
    if candidate["has_alpha"] is not True:
        raise ValueError("candidate_alpha_channel_required")

    catalog_scope, canonical = _catalog_context(
        live_catalog,
        staging_catalog,
        product_id=product_id,
    )
    canonical_volume = _positive_int(
        canonical.get("volume_ml"),
        error="canonical_volume_required",
    )
    if canonical_volume != candidate["volume_ml"]:
        raise ValueError("candidate_volume_does_not_match_canonical_product")

    canonical_concentration = str(canonical.get("concentration") or "").strip()
    if (
        canonical_concentration
        and candidate["concentration"]
        and canonical_concentration != candidate["concentration"]
    ):
        raise ValueError("candidate_concentration_does_not_match_canonical_product")

    if catalog_scope == "live" and _verified_truth_visual_exists(canonical):
        raise ValueError("canonical_product_already_has_verified_product_truth")

    source_path = _safe_candidate_asset(
        candidate["candidate_asset"],
        repo_root=repo_root,
        expected_sha256=candidate["sha256"],
    )
    target_path = _safe_public_asset(
        public_asset,
        public_root=public_root,
        source_path=source_path,
    )

    write_supported = (
        catalog_scope == "staging"
        and candidate["candidate_source"] == "staged_fidelity"
    )
    return {
        "product_id": product_id,
        "candidate_source": candidate["candidate_source"],
        "catalog_scope": catalog_scope,
        "source_candidate_asset": candidate["candidate_asset"],
        "source_sha256": candidate["sha256"].lower(),
        "generator": candidate["generator"],
        "width": candidate["width"],
        "height": candidate["height"],
        "has_alpha": True,
        "approval_basis": candidate["approval_basis"],
        "approved_at": candidate["approved_at"],
        "evidence_url": candidate["evidence_url"],
        "public_asset": public_asset,
        "public_asset_exists": target_path.exists(),
        "will_copy_public_asset": not target_path.exists(),
        "fidelity_status": "verified",
        "provenance": "dufynd_generated",
        "variant": f"{canonical_volume}ml",
        "volume_ml": canonical_volume,
        "concentration": canonical_concentration or candidate["concentration"],
        "generated_media_status": GENERATED_PRODUCT_TRUTH_STATUS,
        "write_supported": write_supported,
        "catalog_promotion": False,
        "public_activation": False,
        "catalog_ready_will_change": False,
        "validation_gate_will_change": "approved_product_image_pending",
        "next_gate": (
            "normal_catalog_promotion_after_all_remaining_gates"
            if write_supported
            else "separate_live_catalog_product_truth_activation_required"
        ),
    }


def apply_staged_registration(
    staging_catalog: dict[str, Any],
    staged_candidates: dict[str, Any],
    plan: dict[str, Any],
    *,
    registered_at: str,
) -> None:
    if plan.get("catalog_scope") != "staging" or plan.get("write_supported") is not True:
        raise ValueError("live_catalog_product_requires_separate_activation_gate")
    if plan.get("candidate_source") != "staged_fidelity":
        raise ValueError("staged_registration_requires_staged_fidelity_candidate")

    product_id = str(plan["product_id"])
    staged = _find_product(staging_catalog, product_id)
    if staged is None:
        raise ValueError("staging_product_not_found")

    media = dict(staged.get("media") or {})
    existing_url = str(media.get("image_url") or "").strip()
    existing_status = str(media.get("image_status") or "").strip()
    if existing_url and (
        existing_url != plan["public_asset"]
        or existing_status != GENERATED_PRODUCT_TRUTH_STATUS
    ):
        raise ValueError("staging_product_already_has_different_image")

    media.update(
        {
            "image_url": plan["public_asset"],
            "image_status": GENERATED_PRODUCT_TRUTH_STATUS,
            "image_reviewed_at": registered_at,
            "image_source_class": "dufynd_generated",
            "image_source_sha256": plan["source_sha256"],
            "image_generator": plan["generator"],
            "image_fidelity_approval_basis": plan["approval_basis"],
            "image_fidelity_approved_at": plan["approved_at"],
            "image_exact_variant_verified": True,
            "image_variant": plan["variant"],
            "image_reference_url": plan["evidence_url"],
        }
    )
    staged["media"] = media

    validation = dict(staged.get("validation") or {})
    validation["catalog_ready"] = bool(validation.get("catalog_ready", False))
    blockers = [
        blocker
        for blocker in list(validation.get("blockers", []) or [])
        if blocker != "approved_product_image_pending"
    ]
    validation["blockers"] = blockers
    staged["validation"] = validation

    candidate = next(
        (
            item
            for item in staged_candidates.get("items", [])
            if str(item.get("product_id") or "").strip() == product_id
        ),
        None,
    )
    if candidate is None:
        raise ValueError("staged_candidate_not_found")
    if str(candidate.get("status") or "").strip() != STAGED_APPROVED_STATUS:
        raise ValueError("staged_candidate_not_human_fidelity_approved")
    if candidate.get("catalog_promotion") is not False:
        raise ValueError("candidate_catalog_promotion_must_be_false")
    if candidate.get("public_activation") is not False:
        raise ValueError("candidate_public_activation_must_be_false")

    candidate["status"] = "human_fidelity_approved_registered_product_truth"
    candidate["source_registration_status"] = "registered_product_truth"
    candidate["registered_public_asset"] = plan["public_asset"]
    candidate["registered_at"] = registered_at
    candidate["catalog_promotion"] = False
    candidate["public_activation"] = False


def copy_public_asset(
    plan: dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
    public_root: Path = DEFAULT_PUBLIC_ROOT,
) -> None:
    source = _safe_candidate_asset(
        plan["source_candidate_asset"],
        repo_root=repo_root,
        expected_sha256=plan["source_sha256"],
    )
    target = _safe_public_asset(
        plan["public_asset"],
        public_root=public_root,
        source_path=source,
    )
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    shutil.copyfile(source, temporary)
    temporary.replace(target)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Register explicit-human-approved DUFYND-generated product truth. "
            "Dry-run by default. Staged products can be registered with --write; "
            "already-live products require a separate activation gate."
        )
    )
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--public-asset", required=True)
    parser.add_argument(
        "--source",
        choices=("auto", "visual_review_queue", "staged_fidelity"),
        default="auto",
    )
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument(
        "--staged-candidates",
        type=Path,
        default=DEFAULT_STAGED_CANDIDATES,
    )
    parser.add_argument("--live-catalog", type=Path, default=DEFAULT_LIVE_CATALOG)
    parser.add_argument(
        "--staging-catalog",
        type=Path,
        default=DEFAULT_STAGING_CATALOG,
    )
    parser.add_argument("--public-root", type=Path, default=DEFAULT_PUBLIC_ROOT)
    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "Register generated product truth in staging and copy its approved "
            "asset. Never promotes catalog_ready or activates a live product."
        ),
    )
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        queue = load_json(args.queue)
        staged_candidates = load_json(args.staged_candidates)
        live_catalog = load_json(args.live_catalog)
        staging_catalog = load_json(args.staging_catalog)
        plan = promotion_plan(
            queue,
            staged_candidates,
            live_catalog,
            staging_catalog,
            product_id=args.product_id,
            public_asset=args.public_asset,
            source=args.source,
            public_root=args.public_root,
        )
        if args.write:
            if plan["write_supported"] is not True:
                raise ValueError(
                    "live_catalog_product_requires_separate_activation_gate"
                )
            registered_at = datetime.now(UTC).isoformat()
            apply_staged_registration(
                staging_catalog,
                staged_candidates,
                plan,
                registered_at=registered_at,
            )
            copy_public_asset(plan, public_root=args.public_root)
            write_json_atomic(args.staging_catalog, staging_catalog)
            write_json_atomic(args.staged_candidates, staged_candidates)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    output = {
        **plan,
        "mode": "WRITE" if args.write else "DRY-RUN",
    }
    if args.machine_readable:
        print(json.dumps(output, ensure_ascii=False))
    else:
        print(
            "DUFYND generated product truth | "
            f"mode={output['mode']} | "
            f"product={output['product_id']} | "
            f"scope={output['catalog_scope']} | "
            f"variant={output['variant']} | "
            f"write_supported={output['write_supported']} | "
            f"next_gate={output['next_gate']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
