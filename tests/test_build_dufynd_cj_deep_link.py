from __future__ import annotations

import pytest
from scripts.build_dufynd_cj_deep_link import build_cj_deep_link


def test_build_notino_cj_deep_link_matches_verified_preflight() -> None:
    url = build_cj_deep_link(
        destination_url=("https://www.notino.de/lattafa/eclaire-eau-de-parfum-unisex/")
    )

    assert url == (
        "https://www.jdoqocy.com/click-101884613-12260695?"
        "url=https%3A%2F%2Fwww.notino.de%2Flattafa%2F"
        "eclaire-eau-de-parfum-unisex%2F"
    )


def test_build_notino_cj_deep_link_rejects_non_notino_destination() -> None:
    with pytest.raises(ValueError, match="destination_url host"):
        build_cj_deep_link(
            destination_url="https://example.com/product",
        )


def test_build_notino_cj_deep_link_requires_verified_tracking_host() -> None:
    with pytest.raises(ValueError, match="tracking_base host"):
        build_cj_deep_link(
            destination_url="https://www.notino.de/product",
            tracking_base="https://example.com/click-1-2",
        )


def test_build_notino_cj_deep_link_requires_https_destination() -> None:
    with pytest.raises(ValueError, match="https"):
        build_cj_deep_link(
            destination_url="http://www.notino.de/product",
        )
