from __future__ import annotations

from scripts.export_scentai_launch_links import (
    build_launch_links,
)


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
        base_url="https://scentai.example",
    )

    assert len(rows) == 6
    assert len(
        {
            (row["channel"], row["content_id"])
            for row in rows
        }
    ) == 6
    assert rows[0]["url"].startswith(
        "https://scentai.example/duftfinder?"
    )
    assert "cmp=launch01" in rows[0]["url"]
    assert "content=creative_01" in rows[0]["url"]
