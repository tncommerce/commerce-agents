"""Offline review contract; no authenticated authorization or publishing capability."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CHECKS = (
    "product_truth",
    "variant_concentration_size",
    "visual_identity",
    "brand_fit",
    "hook",
    "clarity",
    "platform_fit",
    "cta",
    "affiliate_destination",
    "asset_rights",
    "audio_rights",
    "factual_claims",
    "technical_quality",
    "native_mobile_preview",
    "platform_click_path",
    "duplicate_content",
    "dufynd_quality",
)


def revision_hash(package: dict) -> str:
    """Bind review to the entire frozen package, including links and rights refs.

    Actual asset bytes must have SHA-256 digests inside package.assets; changing
    a file at an unchanged URI must invalidate its recorded digest upstream.
    """
    encoded = json.dumps(package, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _digest(value: object) -> bool:
    return (
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    )


def evaluate(document: dict) -> dict:
    reasons = []
    package = document.get("package")
    review = document.get("review")
    if not isinstance(package, dict) or not isinstance(review, dict):
        return _result(["package_and_review_required"])
    maker, checker = package.get("maker_id"), review.get("checker_id")
    if not _text(maker) or not _text(checker):
        reasons.append("identities_required")
    elif maker.strip().casefold() == checker.strip().casefold():
        reasons.append("self_approval_forbidden")
    for field in ("content_id", "campaign_id", "platform", "product_id"):
        if not _text(package.get(field)):
            reasons.append(f"{field}_required")
    assets = package.get("assets")
    if (
        not isinstance(assets, list)
        or not assets
        or any(
            not isinstance(a, dict) or not _text(a.get("uri")) or not _digest(a.get("sha256"))
            for a in assets
        )
    ):
        reasons.append("frozen_asset_digests_required")
    try:
        current_hash = revision_hash(package)
    except (TypeError, ValueError):
        reasons.append("package_not_canonical_json")
        current_hash = None
    if not current_hash or review.get("revision_hash") != current_hash:
        reasons.append("review_revision_mismatch")
    round_number = document.get("revision_round")
    if type(round_number) is not int or not 0 <= round_number <= 2:
        reasons.append("revision_limit_owner_exception_required")
    checks = review.get("checks")
    checks = checks if isinstance(checks, dict) else {}
    for name in CHECKS:
        check = checks.get(name)
        if (
            not isinstance(check, dict)
            or check.get("result") != "PASS"
            or not _text(check.get("evidence_ref"))
        ):
            reasons.append(f"check_not_evidenced:{name}")
    # Platform-native publish contract. This prevents a visually reviewed asset from
    # being posted with an unusable CTA/click surface or an unverified compressed upload.
    publish = package.get("publish_contract")
    if not isinstance(publish, dict):
        reasons.append("publish_contract_required")
    else:
        platform = str(package.get("platform") or "").strip().casefold()
        media_kind = str(publish.get("media_kind") or "").strip().casefold()
        width = publish.get("width_px")
        height = publish.get("height_px")
        score = publish.get("visual_score")
        if type(width) is not int or type(height) is not int or width < 1080 or height < 1080:
            reasons.append("media_resolution_below_publish_floor")
        if (
            not isinstance(score, (int, float))
            or isinstance(score, bool)
            or score < 9.5
            or score > 10
        ):
            reasons.append("visual_score_below_owner_standard")
        if publish.get("native_preview_verified") is not True:
            reasons.append("native_preview_not_verified")
        if publish.get("final_upload_asset_verified") is not True:
            reasons.append("final_upload_asset_not_verified")

        caption = str(package.get("caption") or "")
        cta_mode = str(publish.get("cta_mode") or "").strip().casefold()
        click_surface = str(publish.get("click_surface") or "").strip().casefold()
        if platform == "instagram":
            if media_kind not in {"image", "carousel", "reel", "story"}:
                reasons.append("instagram_media_kind_invalid")
            if media_kind in {"image", "carousel", "reel"} and (
                "http://" in caption or "https://" in caption
            ):
                reasons.append("instagram_raw_caption_url_forbidden")
            if cta_mode not in {"profile_link", "story_link_sticker"}:
                reasons.append("instagram_cta_mode_invalid")
            if cta_mode == "profile_link" and publish.get("profile_link_verified") is not True:
                reasons.append("instagram_profile_link_not_verified")
            if cta_mode == "story_link_sticker" and media_kind != "story":
                reasons.append("instagram_story_link_requires_story")
            if click_surface == "caption_url":
                reasons.append("instagram_caption_url_not_clickable")
        elif platform == "tiktok":
            if media_kind not in {"image", "carousel", "video"}:
                reasons.append("tiktok_media_kind_invalid")
            if publish.get("clickable_website_link_available") is not True:
                if "http://" in caption or "https://" in caption:
                    reasons.append("tiktok_raw_url_without_clickable_surface")
                if cta_mode not in {"comment", "profile", "engagement"}:
                    reasons.append("tiktok_nonclickable_cta_invalid")
        elif platform == "youtube":
            if media_kind != "video":
                reasons.append("youtube_video_required")
            if cta_mode not in {"profile_link", "description_link"}:
                reasons.append("youtube_cta_mode_invalid")

    # Scores, Owner permission, or an existing published state cannot bypass QA.
    hard_fails = review.get("hard_fails")
    if not isinstance(hard_fails, list) or hard_fails:
        reasons.append("hard_fail_or_missing_hard_fail_assessment")
    return _result(reasons)


def _result(reasons: list[str]) -> dict:
    return {
        "stage": "REVISION_REQUIRED" if reasons else "READY_FOR_OWNER_APPROVAL",
        "reasons": reasons,
        "publication_authorized": False,
        "authority": "OFFLINE_CONTRACT_ONLY",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        if args.input.stat().st_size > 262144:
            raise ValueError("input exceeds limit")
        document = json.loads(args.input.read_text())
        if not isinstance(document, dict):
            raise ValueError("object required")
        result = evaluate(document)
    except (OSError, ValueError, TypeError):
        result = _result(["invalid_input"])
    print(json.dumps(result, sort_keys=True))
    return 1 if result["reasons"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
