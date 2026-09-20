from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LegacyPreviewPolicy:
    render: bool
    reason: str


def evaluate_legacy_preview_policy(
    strategy: dict[str, Any] | None,
    *,
    force: bool = False,
) -> LegacyPreviewPolicy:
    if force:
        return LegacyPreviewPolicy(
            render=True,
            reason="manual_force_requested",
        )

    if not strategy:
        return LegacyPreviewPolicy(
            render=True,
            reason="no_content_strategy_found",
        )

    active_track = str(strategy.get("active_track") or "").strip()
    legacy_state = str(strategy.get("legacy_pilot_batches") or "").strip()

    if active_track == "high_end_rnd" and legacy_state == "hold":
        return LegacyPreviewPolicy(
            render=False,
            reason="legacy_pilots_on_hold_for_high_end_rnd",
        )

    return LegacyPreviewPolicy(
        render=True,
        reason="legacy_pilot_rendering_active",
    )


def load_strategy(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("DUFYND content strategy must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Decide whether the legacy DUFYND pilot previews should be "
            "re-rendered for the current content strategy."
        )
    )
    parser.add_argument(
        "--strategy",
        type=Path,
        default=Path("examples/retail/data/dufynd_content_strategy.json"),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Render even when the legacy pilot batches are on hold.",
    )
    parser.add_argument(
        "--github-output",
        action="store_true",
        help="Print GitHub Actions output key/value lines.",
    )
    args = parser.parse_args()

    try:
        policy = evaluate_legacy_preview_policy(
            load_strategy(args.strategy),
            force=args.force,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if args.github_output:
        print(f"render={'true' if policy.render else 'false'}")
        print(f"reason={policy.reason}")
    else:
        print(
            json.dumps(
                {
                    "render": policy.render,
                    "reason": policy.reason,
                },
                ensure_ascii=False,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
