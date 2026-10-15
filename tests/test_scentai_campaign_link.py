from __future__ import annotations

import pytest
from scripts.build_scentai_campaign_link import build_campaign_url


def test_campaign_link_contains_standardized_attribution() -> None:
    link = build_campaign_url(
        base_url="https://dufynd.example",
        landing_path="/parfum-alternativen",
        channel="tiktok",
        campaign_id="launch01",
        content_id="imagination_dupe_03",
    )

    assert link == (
        "https://dufynd.example/parfum-alternativen"
        "?src=tiktok&cmp=launch01&content=imagination_dupe_03"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("campaign_id", "launch campaign"),
        ("content_id", "email@example.com"),
    ],
)
def test_campaign_link_rejects_free_form_attribution(
    field: str,
    value: str,
) -> None:
    kwargs = {
        "base_url": "https://dufynd.example",
        "landing_path": "/duftfinder",
        "channel": "instagram",
        "campaign_id": "launch01",
        "content_id": "gift_guide_01",
    }
    kwargs[field] = value

    with pytest.raises(ValueError):
        build_campaign_url(**kwargs)


def test_campaign_link_rejects_unknown_channel() -> None:
    with pytest.raises(ValueError):
        build_campaign_url(
            base_url="https://dufynd.example",
            landing_path="/duftfinder",
            channel="random-source",
            campaign_id="launch01",
            content_id="video_01",
        )


def test_campaign_link_requires_public_https_origin() -> None:
    with pytest.raises(ValueError):
        build_campaign_url(
            base_url="http://dufynd.example",
            landing_path="/duftfinder",
            channel="youtube",
            campaign_id="launch01",
            content_id="video_01",
        )


@pytest.mark.parametrize("suffix", ["/duft", "/duft/", "?src=old", "#old"])
def test_campaign_link_rejects_non_origin_base(suffix: str) -> None:
    with pytest.raises(ValueError, match="origin"):
        build_campaign_url(
            base_url="https://dufynd.de" + suffix,
            landing_path="/duft/rabanne-1-million",
            channel="tiktok",
            campaign_id="check",
            content_id="check",
        )


@pytest.mark.parametrize("base", ["https://dufynd.de", " https://dufynd.de/ "])
@pytest.mark.parametrize(
    "landing,channel,campaign,content",
    [
        ("/duft", "tiktok", "tt_bio_launch_20261011", "profile_bio"),
        (
            "/duft/rabanne-1-million",
            "youtube",
            "yt_1million_v8DlVXi-Fj8_p1",
            "one_million_example61_01",
        ),
    ],
)
def test_observed_profile_targets_round_trip_offline(
    base: str, landing: str, channel: str, campaign: str, content: str
) -> None:
    assert (
        build_campaign_url(
            base_url=base,
            landing_path=landing,
            channel=channel,
            campaign_id=campaign,
            content_id=content,
        )
        == f"https://dufynd.de{landing}?src={channel}&cmp={campaign}&content={content}"
    )
