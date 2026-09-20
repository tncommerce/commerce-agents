from __future__ import annotations

from pathlib import Path

STOREFRONT_ROOT = Path("examples/retail/storefront-web")
TEXT_SUFFIXES = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".css",
    ".md",
    ".json",
    ".svg",
}
IGNORED_PARTS = {
    "node_modules",
    ".next",
}


def test_dufynd_public_storefront_has_no_legacy_scentai_brand() -> None:
    offenders: list[str] = []

    for path in STOREFRONT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in IGNORED_PARTS for part in path.parts):
            continue

        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
        if "SCENTAI" in text or "Scentai" in text:
            offenders.append(str(path))

    assert offenders == [], (
        "Legacy SCENTAI branding remains in public storefront source: "
        + ", ".join(sorted(offenders))
    )
