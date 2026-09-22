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
