import json
from copy import deepcopy
from pathlib import Path

import pytest
from scripts.build_scentai_campaign_link import build_campaign_url
from scripts.check_dufynd_content_review import CHECKS, evaluate, revision_hash


def reviewed():
    package = {
        "maker_id": "maker-A",
        "content_id": "creative-1",
        "campaign_id": "campaign-1",
        "platform": "youtube",
        "product_id": "product-1",
        "assets": [{"uri": "internal://frozen-master", "sha256": "a" * 64}],
        "caption": "Exact variant, transparent affiliate disclosure",
        "affiliate_destination": "https://example.org/approved-offer",
        "publish_contract": {
            "media_kind": "video",
            "width_px": 1080,
            "height_px": 1920,
            "visual_score": 9.7,
            "native_preview_verified": True,
            "final_upload_asset_verified": True,
            "cta_mode": "profile_link",
            "click_surface": "profile_link",
            "profile_link_verified": True,
            "clickable_website_link_available": True,
        },
    }
    return {
        "package": package,
        "revision_round": 0,
        "review": {
            "checker_id": "checker-B",
            "revision_hash": revision_hash(package),
            "hard_fails": [],
            "checks": {
                name: {"result": "PASS", "evidence_ref": f"internal://review/{name}"}
                for name in CHECKS
            },
        },
    }


def test_independent_evidenced_review_only_reaches_owner_gate():
    result = evaluate(reviewed())
    assert result["stage"] == "READY_FOR_OWNER_APPROVAL"
    assert result["publication_authorized"] is False
    assert result["authority"] == "OFFLINE_CONTRACT_ONLY"


def test_self_approval_cannot_be_bypassed_by_owner_flag_or_score():
    doc = reviewed()
    doc["review"].update(checker_id="  MAKER-a ", score=100)
    doc["owner_approval"] = True
    assert "self_approval_forbidden" in evaluate(doc)["reasons"]


@pytest.mark.parametrize("name", CHECKS)
def test_each_mandatory_check_blocks_even_with_perfect_average(name):
    doc = reviewed()
    doc["review"]["checks"][name]["result"] = "FAIL"
    doc["review"]["average_score"] = 100
    assert f"check_not_evidenced:{name}" in evaluate(doc)["reasons"]


@pytest.mark.parametrize("field", ["caption", "product_id", "affiliate_destination"])
def test_changed_package_requires_fresh_independent_review(field):
    doc = reviewed()
    doc["package"][field] = "changed"
    assert "review_revision_mismatch" in evaluate(doc)["reasons"]


def test_changed_asset_or_missing_digest_invalidates_review():
    doc = reviewed()
    doc["package"]["assets"][0]["sha256"] = "b" * 64
    assert "review_revision_mismatch" in evaluate(doc)["reasons"]
    doc["package"]["assets"][0]["sha256"] = None
    assert "frozen_asset_digests_required" in evaluate(doc)["reasons"]


def test_revision_requires_full_new_review_and_is_bounded():
    doc = reviewed()
    doc["review"]["hard_fails"] = ["wrong_bottle"]
    assert evaluate(doc)["stage"] == "REVISION_REQUIRED"
    revised = deepcopy(doc)
    revised["package"]["assets"][0]["sha256"] = "b" * 64
    revised["revision_round"] = 1
    revised["review"]["hard_fails"] = []
    assert "review_revision_mismatch" in evaluate(revised)["reasons"]
    revised["review"]["revision_hash"] = revision_hash(revised["package"])
    assert evaluate(revised)["stage"] == "READY_FOR_OWNER_APPROVAL"
    revised["revision_round"] = 3
    assert "revision_limit_owner_exception_required" in evaluate(revised)["reasons"]


def test_unknown_or_evidence_free_checks_fail_closed():
    doc = reviewed()
    doc["review"]["checks"]["asset_rights"]["evidence_ref"] = None
    del doc["review"]["checks"]["audio_rights"]
    doc["review"]["hard_fails"] = None
    assert len(evaluate(doc)["reasons"]) == 3
    assert evaluate({})["stage"] == "REVISION_REQUIRED"


def test_first_loop_links_preserve_creative_and_bind_observed_posts():
    path = Path(__file__).resolve().parents[1] / "docs/supervisor/dufynd-first-revenue-loop.json"
    manifest = json.loads(path.read_text())
    for post in manifest["platforms"]:
        expected = build_campaign_url(
            base_url="https://dufynd.de",
            landing_path="/duft/rabanne-1-million",
            channel=post["platform"],
            campaign_id=manifest["attribution_campaign_id"],
            content_id=manifest["content_id"],
        )
        assert post["proposed_product_url"] == expected
        assert post["platform_content_id"]
        assert post["post_metadata_verified"] is True
        assert post["post_attribution_from_profile_link_proven"] is False
    assert all(value is None for value in manifest["revenue"].values())
    assert manifest["experiment"]["publication_authorized"] is False


def test_instagram_raw_caption_url_and_unverified_profile_link_fail_closed():
    doc = reviewed()
    doc["package"]["platform"] = "instagram"
    doc["package"]["caption"] = "Mehr auf https://dufynd.de/duft/test"
    doc["package"]["publish_contract"].update(
        media_kind="image",
        cta_mode="profile_link",
        click_surface="caption_url",
        profile_link_verified=False,
    )
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    reasons = evaluate(doc)["reasons"]
    assert "instagram_raw_caption_url_forbidden" in reasons
    assert "instagram_caption_url_not_clickable" in reasons
    assert "instagram_profile_link_not_verified" in reasons


def test_low_resolution_or_unverified_native_preview_blocks_even_at_owner_score():
    doc = reviewed()
    doc["package"]["publish_contract"].update(
        width_px=720,
        height_px=1280,
        visual_score=10,
        native_preview_verified=False,
    )
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    reasons = evaluate(doc)["reasons"]
    assert "media_resolution_below_publish_floor" in reasons
    assert "native_preview_not_verified" in reasons


def test_tiktok_raw_url_is_rejected_when_no_clickable_website_surface_exists():
    doc = reviewed()
    doc["package"]["platform"] = "tiktok"
    doc["package"]["caption"] = "Duftprofil: https://dufynd.de/duft/test"
    doc["package"]["publish_contract"].update(
        media_kind="video",
        cta_mode="engagement",
        click_surface="none",
        clickable_website_link_available=False,
    )
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    assert "tiktok_raw_url_without_clickable_surface" in evaluate(doc)["reasons"]


def test_instagram_profile_link_path_can_pass_when_native_asset_is_verified():
    doc = reviewed()
    doc["package"]["platform"] = "instagram"
    doc["package"]["content_kind"] = "education"
    doc["package"]["caption"] = "Duftprofil + Kaufoptionen → Link im Profil."
    doc["package"]["publish_contract"].update(
        media_kind="carousel",
        cta_mode="profile_link",
        click_surface="profile_link",
        profile_link_verified=True,
        clickable_website_link_available=True,
        audio_contract={
            "mode": "instagram_native_music",
            "delivery": "instagram_native_app",
            "commercial_rights_evidence_ref": "internal://evidence/cleared-track",
            "audible_preview_evidence_ref": "internal://qa/ig-native-prelisten",
            "audible_preview_verified": True,
            "audio_score": 9.6,
            "commercial_music_rights_verified": True,
            "native_track_selected_and_preheard": True,
        },
    )
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    assert evaluate(doc)["stage"] == "READY_FOR_OWNER_APPROVAL"


def audio_ready(platform="instagram", media_kind="reel", kind="meme"):
    doc = reviewed()
    doc["package"]["platform"] = platform
    doc["package"]["content_kind"] = kind
    doc["package"]["publish_contract"].update(
        media_kind=media_kind,
        genuine_motion_verified=True,
        audio_contract={
            "mode": "embedded_video",
            "delivery": "metricool_auto",
            "commercial_rights_evidence_ref": "internal://rights/original-score-commercial",
            "audible_preview_evidence_ref": "internal://qa/full-playback-device",
            "audible_preview_verified": True,
            "audio_score": 9.7,
            "commercial_music_rights_verified": True,
            "final_video_sha256": "a" * 64,
            "audio_codec": "aac",
            "audio_stream_evidence_ref": "internal://ffprobe/aac-and-listening-audit",
            "full_playback_verified": True,
            "timing_verified": True,
            "loudness_verified": True,
        },
    )
    if platform == "tiktok":
        doc["package"]["publish_contract"]["cta_mode"] = "engagement"
        doc["package"]["publish_contract"]["clickable_website_link_available"] = False
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    return doc


def test_silent_instagram_and_tiktok_memes_are_never_ready_by_default():
    for platform, kind in (("instagram", "image"), ("instagram", "reel"), ("tiktok", "image")):
        doc = audio_ready(platform, kind)
        del doc["package"]["publish_contract"]["audio_contract"]
        doc["review"]["revision_hash"] = revision_hash(doc["package"])
        assert "audio_contract_required" in evaluate(doc)["reasons"]


def test_instagram_metricool_image_cannot_claim_music_via_reel_configuration():
    doc = audio_ready("instagram", "image")
    doc["package"]["publish_contract"]["audio_contract"].update(
        mode="metricool_reel_library",
        audio_id="123456789",
        facebook_connection_verified=True,
    )
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    assert "instagram_photo_audio_requires_native_handoff" in evaluate(doc)["reasons"]


def test_instagram_native_image_is_reviewable_only_after_manual_audio_prelistening():
    doc = audio_ready("instagram", "image")
    doc["package"]["publish_contract"]["audio_contract"].update(
        mode="instagram_native_music",
        delivery="instagram_native_app",
        native_track_selected_and_preheard=True,
    )
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    assert evaluate(doc)["stage"] == "READY_FOR_OWNER_APPROVAL"
    assert evaluate(doc)["publication_authorized"] is False


def test_metricool_instagram_reel_requires_proven_facebook_connection_and_audio_id():
    doc = audio_ready("instagram", "reel")
    doc["package"]["publish_contract"]["audio_contract"].update(
        mode="metricool_reel_library",
        delivery="metricool_auto",
    )
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    reasons = evaluate(doc)["reasons"]
    assert "instagram_reel_facebook_connection_unverified" in reasons
    assert "instagram_reel_audio_id_required" in reasons
    doc["package"]["publish_contract"]["audio_contract"].update(
        facebook_connection_verified=True,
        audio_id="123456789",
        instagram_business_verified=True,
        connection_evidence_ref="qa:connection",
        native_track_selected_and_preheard=True,
    )
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    assert evaluate(doc)["stage"] == "READY_FOR_OWNER_APPROVAL"


def test_reel_audio_stream_must_be_evidenced_and_bound_to_exact_frozen_video():
    doc = audio_ready("instagram", "reel")
    audio = doc["package"]["publish_contract"]["audio_contract"]
    audio["final_video_sha256"] = "b" * 64
    audio["audio_codec"] = None
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    assert "embedded_audio_video_digest_mismatch" in evaluate(doc)["reasons"]
    assert "embedded_audio_stream_unverified" in evaluate(doc)["reasons"]


def test_tiktok_photos_need_selected_native_music_not_random_autoadd():
    doc = audio_ready("tiktok", "image")
    doc["package"]["publish_contract"]["audio_contract"].update(auto_add_music=True)
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    assert "tiktok_photo_requires_preheard_native_audio" in evaluate(doc)["reasons"]
    audio = doc["package"]["publish_contract"]["audio_contract"]
    audio.update(
        mode="tiktok_native_music",
        delivery="metricool_notification",
        native_track_selected_and_preheard=True,
    )
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    assert evaluate(doc)["stage"] == "READY_FOR_OWNER_APPROVAL"


def test_meme_cannot_use_owner_exception_to_publish_silent():
    doc = audio_ready("instagram", "image")
    doc["package"]["publish_contract"]["audio_contract"] = {
        "mode": "intentional_silence",
        "owner_silence_exception_ref": "owner://approve-silence",
        "silence_editorial_reason": "minimal photography",
    }
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    assert "silent_meme_forbidden" in evaluate(doc)["reasons"]


def test_editorial_silence_needs_explicit_owner_exception_and_reason():
    doc = audio_ready("instagram", "carousel", kind="education")
    doc["package"]["publish_contract"]["audio_contract"] = {
        "mode": "intentional_silence",
        "silence_editorial_reason": "reader-controlled educational slides",
    }
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    assert "intentional_silence_owner_exception_missing" in evaluate(doc)["reasons"]
    doc["package"]["publish_contract"]["audio_contract"]["owner_silence_exception_ref"] = (
        "owner://educational-silence"
    )
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    assert evaluate(doc)["stage"] == "READY_FOR_OWNER_APPROVAL"


def test_change_in_audio_track_invalidates_prior_review_hash():
    doc = audio_ready("instagram", "reel")
    assert evaluate(doc)["stage"] == "READY_FOR_OWNER_APPROVAL"
    doc["package"]["publish_contract"]["audio_contract"]["audio_score"] = 9.3
    reasons = evaluate(doc)["reasons"]
    assert "review_revision_mismatch" in reasons
    assert "audio_quality_below_owner_standard" in reasons


def test_tiktok_embedded_audio_video_with_proven_aac_is_reviewable():
    doc = audio_ready("tiktok", "video")
    assert evaluate(doc)["stage"] == "READY_FOR_OWNER_APPROVAL"
    assert evaluate(doc)["publication_authorized"] is False


@pytest.mark.parametrize("width,height", [(1080, 1080), (1080, 1350), (720, 1280), (1920, 1080)])
def test_social_video_requires_real_vertical_resolution(width, height):
    doc = audio_ready()
    doc["package"]["publish_contract"].update(width_px=width, height_px=height)
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    assert "video_requires_1080x1920_9_16" in evaluate(doc)["reasons"]


def test_still_image_wrapped_as_video_does_not_pass():
    doc = audio_ready()
    doc["package"]["publish_contract"]["genuine_motion_verified"] = False
    doc["review"]["revision_hash"] = revision_hash(doc["package"])
    assert "genuine_video_motion_not_verified" in evaluate(doc)["reasons"]
