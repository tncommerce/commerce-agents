from __future__ import annotations

import pytest
from scripts.build_dufynd_tracking_url import (
    build_tracking_url,
)


def test_build_tracking_url_for_social_content() -> None:
    url = build_tracking_url(
        base_url="https://dufynd.de",
        path="/parfum-alternativen",
        source="tiktok",
        campaign_id="launch01",
        content_id="genesis_naxos_01",
    )

    assert url == (
        "https://dufynd.de/parfum-alternativen"
        "?src=tiktok&cmp=launch01&content=genesis_naxos_01"
    )


def test_build_tracking_url_rejects_free_form_campaign() -> None:
    with pytest.raises(ValueError, match="campaign_id"):
        build_tracking_url(
            base_url="https://dufynd.de",
            path="/",
            source="instagram",
            campaign_id="launch campaign",
            content_id="video01",
        )


def test_build_tracking_url_requires_https() -> None:
    with pytest.raises(ValueError, match="https"):
        build_tracking_url(
            base_url="http://dufynd.de",
            path="/",
            source="youtube",
            campaign_id="launch01",
            content_id="video01",
        )
