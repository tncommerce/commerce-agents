from __future__ import annotations

import json
from pathlib import Path

BRAND_ROOT = Path(
    "examples/retail/storefront-web/public/brand"
)
BRAND_PACK = Path(
    "examples/retail/data/dufynd_brand_pack.json"
)


def test_dufynd_brand_master_assets_exist_and_are_current() -> None:
    expected = {
        "dufynd-mark.svg",
        "dufynd-logo-lockup.svg",
        "dufynd-logo-lockup-light.svg",
    }

    assert expected == {
        path.name for path in BRAND_ROOT.glob("*.svg")
    }

    for filename in expected:
        text = (BRAND_ROOT / filename).read_text(
            encoding="utf-8"
        )
        assert "DUFYND" in text
        assert "SCENTAI" not in text


def test_dufynd_brand_pack_references_existing_assets() -> None:
    payload = json.loads(
        BRAND_PACK.read_text(encoding="utf-8")
    )

    assert payload["brand"] == "DUFYND"
    assert payload["status"] == "operational_master"

    for value in payload["logo_assets"].values():
        relative = value.removeprefix("/brand/")
        assert (BRAND_ROOT / relative).is_file()

    assert any(
        "Never ask a video model" in rule
        for rule in payload["ai_video_rules"]
    )
