"""Keep every example Next.js workspace at or above the repository security baseline."""

from __future__ import annotations

import json
import re
from pathlib import Path

EXAMPLES = Path("examples")
APP_MANIFESTS = sorted(EXAMPLES.glob("*/merchant-web/package.json")) + sorted(
    EXAMPLES.glob("*/storefront-web/package.json")
)
LOCKFILE = EXAMPLES / "package-lock.json"
MIN_NEXT = (16, 3, 3)
VERSION = re.compile(r"^[~^]?([0-9]+)\.([0-9]+)\.([0-9]+)$")


def _version(value: str) -> tuple[int, int, int]:
    match = VERSION.fullmatch(value.strip())
    assert match, f"Unsupported Next.js version range: {value}"
    return tuple(int(part) for part in match.groups())


def test_all_example_apps_require_safe_next_baseline() -> None:
    assert len(APP_MANIFESTS) == 8

    for path in APP_MANIFESTS:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        required = manifest["dependencies"]["next"]
        assert _version(required) >= MIN_NEXT, f"{path}: Next.js {required} is below 16.3.3"


def test_workspace_lock_installs_safe_next_version() -> None:
    lock = json.loads(LOCKFILE.read_text(encoding="utf-8"))
    installed = lock["packages"]["node_modules/next"]["version"]

    assert _version(installed) >= MIN_NEXT


def test_workspace_lock_ranges_match_app_manifests() -> None:
    lock = json.loads(LOCKFILE.read_text(encoding="utf-8"))

    for path in APP_MANIFESTS:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        workspace_key = path.relative_to(EXAMPLES).parent.as_posix()
        locked_requirement = lock["packages"][workspace_key]["dependencies"]["next"]

        assert locked_requirement == manifest["dependencies"]["next"]
        assert _version(locked_requirement) >= MIN_NEXT
