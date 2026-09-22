from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from scripts.build_scentai_campaign_link import build_campaign_url

DEFAULT_PLAN = Path("examples/retail/data/scentai_launch_content_plan.json")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_launch_links(plan: dict, *, base_url: str) -> list[dict]:
    campaign_id = str(plan.get("campaign_id") or "").strip()
    channels = plan.get("channels")
    content_rows = plan.get("content")

    if not campaign_id:
        raise ValueError("Launch plan requires campaign_id")
    if not isinstance(channels, list) or not channels:
        raise ValueError("Launch plan requires channels")
    if not isinstance(content_rows, list) or not content_rows:
        raise ValueError("Launch plan requires content rows")

    rows: list[dict] = []
    for content in content_rows:
        content_id = str(content.get("content_id") or "").strip()
        landing_path = str(content.get("landing_path") or "").strip()

        if not content_id or not landing_path:
            raise ValueError("Every content row requires content_id and landing_path")

        for channel in channels:
            link = build_campaign_url(
                base_url=base_url,
                landing_path=landing_path,
                channel=str(channel),
                campaign_id=campaign_id,
                content_id=content_id,
            )
            rows.append(
                {
                    "campaign_id": campaign_id,
                    "content_id": content_id,
                    "format": content.get("format"),
                    "channel": str(channel),
                    "landing_path": landing_path,
                    "url": link,
                }
            )

    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export standardized DUFYND launch links for every planned "
            "creative and organic channel."
        )
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN,
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("NEXT_PUBLIC_SITE_URL", ""),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    args = parser.parse_args()

    if not args.base_url:
        parser.error("--base-url or NEXT_PUBLIC_SITE_URL is required")

    try:
        rows = build_launch_links(
            load_json(args.plan),
            base_url=args.base_url,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    payload = {
        "plan": str(args.plan),
        "link_count": len(rows),
        "links": rows,
    }

    if args.output is not None:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        args.output.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    if args.machine_readable or args.output is None:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"DUFYND launch links | count={len(rows)} | output={args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
