"""Keep DUFYND runtime accord labels complete for live and staged fragrances."""

from __future__ import annotations

import json
import re
from pathlib import Path

LIVE = Path("examples/retail/data/scentai_products.json")
STAGING = Path("examples/retail/data/scentai_catalog_staging.json")
MOCK_RETAIL = Path("examples/retail/api/mock_retail.py")

ENTRY = re.compile(r'^\s*"(?P<key>[^"]+)":\s*"(?P<label>[^"]+)",\s*$', re.MULTILINE)


def _accords(path: Path, *, staged: bool) -> set[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    values: set[str] = set()

    for product in payload["products"]:
        profile = product.get("fragrance_profile") or {}
        for accord in profile.get("community_accords", []):
            if str(accord).strip():
                values.add(str(accord).strip().lower())

    return values


def _runtime_labels() -> dict[str, str]:
    source = MOCK_RETAIL.read_text(encoding="utf-8")
    block = source.split("accord_labels_de = {", 1)[1].split("        }", 1)[0]
    return {match["key"].lower(): match["label"] for match in ENTRY.finditer(block)}


def test_runtime_labels_cover_live_and_staged_accords() -> None:
    labels = _runtime_labels()
    required = _accords(LIVE, staged=False) | _accords(STAGING, staged=True)

    missing = sorted(required - labels.keys())

    assert not missing, f"Missing German runtime accord labels: {missing}"
    assert all(labels[accord].strip() for accord in required)
