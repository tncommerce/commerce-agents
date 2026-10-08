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


def _audio_publish_reasons(package: dict, publish: dict, *, platform: str, media_kind: str) -> list[str]:
    """Fail closed on silent social memes and unsupported automatic music flows.

    This validates submitted review evidence, not the audio file itself. A separate
    independent listening/rights check and post-publication verification remain
    required; nothing here grants permission to schedule or publish.
    """
    if platform not in {"instagram", "tiktok"}:
        return []

    reasons: list[str] = []
    kind = str(package.get("content_kind") or "").strip().casefold()
    if kind not in {"meme", "editorial", "education", "product"}:
        reasons.append("social_content_kind_required")
    audio = publish.get("audio_contract")
    if not isinstance(audio, dict):
        return reasons + ["audio_contract_required"]

    mode = str(audio.get("mode") or "").strip().casefold()
    delivery = str(audio.get("delivery") or "").strip().casefold()
    if mode == "intentional_silence":
        if kind == "meme":
            reasons.append("silent_meme_forbidden")
        if kind not in {"editorial", "education"}:
            reasons.append("silent_exception_content_kind_invalid")
        if not _text(audio.get("owner_silence_exception_ref")) or not _text(
            audio.get("silence_editorial_reason")
        ):
            reasons.append("intentional_silence_owner_exception_missing")
        return reasons

    # Every audible post needs specific independently reviewable evidence.
    for field in ("commercial_rights_evidence_ref", "audible_preview_evidence_ref"):
        if not _text(audio.get(field)):
            reasons.append(f"audio_{field}_required")
    if audio.get("audible_preview_verified") is not True:
        reasons.append("audio_playback_not_verified")
    score = audio.get("audio_score")
    if (
        not isinstance(score, (int, float))
        or isinstance(score, bool)
        or not 9.5 <= score <= 10
    ):
        reasons.append("audio_quality_below_owner_standard")
    if audio.get("commercial_music_rights_verified") is not True:
        reasons.append("audio_commercial_rights_not_verified")

    if platform == "instagram":
        if media_kind in {"image", "carousel", "story"}:
            # Third-party Instagram image/carousel auto-posting carries no
            # selectable music track; a native Instagram handoff is mandatory.
            if mode != "instagram_native_music" or delivery not in {
                "instagram_native_app", "metricool_notification"
            }:
                reasons.append("instagram_photo_audio_requires_native_handoff")
            if audio.get("native_track_selected_and_preheard") is not True:
                reasons.append("instagram_native_audio_not_preheard")
        elif media_kind == "reel":
            if mode == "metricool_reel_library":
                # Metricool supports audioConfiguration.audioId on REEL only
                # when the business Instagram account uses Facebook Login.
                if delivery != "metricool_auto":
                    reasons.append("instagram_reel_music_delivery_invalid")
                if audio.get("facebook_connection_verified") is not True:
                    reasons.append("instagram_reel_facebook_connection_unverified")
                if not _text(audio.get("audio_id")):
                    reasons.append("instagram_reel_audio_id_required")
            elif mode == "embedded_video":
                if not _text(audio.get("final_video_sha256")) or not _digest(
                    audio.get("final_video_sha256")
                ):
                    reasons.append("embedded_audio_final_video_digest_required")
                elif audio["final_video_sha256"] not in {
                    a.get("sha256") for a in package.get("assets", []) if isinstance(a, dict)
                }:
                    reasons.append("embedded_audio_video_digest_mismatch")
                if audio.get("audio_codec") != "aac" or not _text(
                    audio.get("audio_stream_evidence_ref")
                ):
                    reasons.append("embedded_audio_stream_unverified")
            elif mode == "instagram_native_music":
                if delivery not in {"instagram_native_app", "metricool_notification"}:
                    reasons.append("instagram_native_reel_requires_manual_handoff")
                if audio.get("native_track_selected_and_preheard") is not True:
                    reasons.append("instagram_native_audio_not_preheard")
            else:
                reasons.append("instagram_reel_audio_mode_invalid")
    elif media_kind in {"image", "carousel"}:
        # TikTok autoAddMusic picks an unpredictable track; it is not a
        # quality-assured replacement for selecting and auditioning a sound.
        if mode != "tiktok_native_music" or delivery not in {
            "tiktok_native_app", "metricool_notification"
        }:
            reasons.append("tiktok_photo_requires_preheard_native_audio")
        if audio.get("native_track_selected_and_preheard") is not True:
            reasons.append("tiktok_native_audio_not_preheard")
    elif media_kind == "video":
        if mode == "embedded_video":
            if not _digest(audio.get("final_video_sha256")) or audio[
                "final_video_sha256"
            ] not in {
                a.get("sha256") for a in package.get("assets", []) if isinstance(a, dict)
            }:
                reasons.append("embedded_audio_video_digest_mismatch")
            if audio.get("audio_codec") != "aac" or not _text(
                audio.get("audio_stream_evidence_ref")
            ):
                reasons.append("embedded_audio_stream_unverified")
        elif mode == "tiktok_native_music":
            if delivery not in {"tiktok_native_app", "metricool_notification"} or (
                audio.get("native_track_selected_and_preheard") is not True
            ):
                reasons.append("tiktok_native_video_requires_audio_handoff")
        else:
            reasons.append("tiktok_video_audio_mode_invalid")
    return reasons


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

        reasons.extend(
            _audio_publish_reasons(package, publish, platform=platform, media_kind=media_kind)
        )

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
