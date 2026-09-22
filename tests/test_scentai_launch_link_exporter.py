from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from scripts.export_scentai_launch_links import (
    build_launch_links,
)

REAL_PLAN = Path("examples/retail/data/scentai_launch_content_plan.json")
CANONICAL_SITE = "https://dufynd.de"


def test_launch_link_exporter_builds_one_link_per_channel_and_content() -> None:
    plan = {
        "campaign_id": "launch01",
        "channels": ["tiktok", "instagram", "youtube"],
        "content": [
            {
                "content_id": "creative_01",
                "format": "top3",
                "landing_path": "/duftfinder",
            },
            {
                "content_id": "creative_02",
                "format": "dupe_battle",
                "landing_path": "/parfum-alternativen",
            },
        ],
    }

    rows = build_launch_links(
        plan,
        base_url="https://dufynd.example",
    )

    assert len(rows) == 6
    assert len({(row["channel"], row["content_id"]) for row in rows}) == 6
    assert rows[0]["url"].startswith("https://dufynd.example/duftfinder?")
    assert "cmp=launch01" in rows[0]["url"]
    assert "content=creative_01" in rows[0]["url"]


def test_real_dufynd_launch_plan_exports_45_canonical_links() -> None:
    plan = json.loads(REAL_PLAN.read_text(encoding="utf-8-sig"))
    rows = build_launch_links(plan, base_url=CANONICAL_SITE)

    assert len(plan["content"]) == 15
    assert plan["channels"] == ["tiktok", "instagram", "youtube"]
    assert len(rows) == 45
    assert len({(row["channel"], row["content_id"]) for row in rows}) == 45

    expected_content_ids = {row["content_id"] for row in plan["content"]}
    assert {row["content_id"] for row in rows} == expected_content_ids

    for row in rows:
        parsed = urlparse(row["url"])
        query = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert parsed.netloc == "dufynd.de"
        assert parsed.path == row["landing_path"]
        assert query == {
            "src": [row["channel"]],
            "cmp": ["launch01"],
            "content": [row["content_id"]],
        }
        assert "scentai" not in row["url"].casefold()
