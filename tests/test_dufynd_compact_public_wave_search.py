"""Publicly released DUFYND fragrance names must not remain negative search fixtures."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path("examples/retail")
SCRIPT = ROOT / "storefront-web/scripts/compact-fragrance-search-qa.mjs"
RELEASED = ROOT / "storefront-web/lib/generated/released-profiles.json"
APPROVALS = ROOT / "data/dufynd_release_authorizations.json"


def test_exact_release_variants_replace_the_stale_negative_search_list() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    released = json.loads(RELEASED.read_text(encoding="utf-8"))["profiles"]
    approvals = json.loads(APPROVALS.read_text(encoding="utf-8"))["approvals"]
    owner_approved = {
        row["product_id"]
        for row in approvals
        if row["publication_approved"] is True and row["indexing_approved"] is True
    }
    cases = {
        "SC-CAROLINA-HERRERA-GOOD-GIRL-EDP-80": "GoodGirl",
        "SC-CHANEL-COCO-MADEMOISELLE-EDP-100": "CocoMademoiselle",
        "SC-GUERLAIN-MON-GUERLAIN-EDP-100": "MonGuerlain",
        "SC-PRADA-PARADOXE-EDP-90": "Prada Paradoxe",
        "SC-BURBERRY-GODDESS-EDP-100": "Burberry Goddess",
    }
    assert len(released) == len(owner_approved) == 20
    assert cases.keys() <= owner_approved
    for product_id, query in cases.items():
        record = next(row for row in released if row["product_id"] == product_id)
        assert record["indexing_approved"] is True
        assert record["seo"]["public_path"].startswith("/duft/")
        assert f"id:'{product_id}'" in source
        assert f"query:'{query}'" in source

    assert "const nowReleased=[" in source
    neg = source.split("const negatives=[", 1)[1].split("for(const query of negatives)", 1)[0]
    assert "'Widian London'" in neg
    assert "'UnknownFragranceXYZ'" in neg
    for query in (
        "GoodGirl",
        "CocoMademoiselle",
        "MonGuerlain",
        "PradaParadoxe",
        "BurberryGoddess",
    ):
        assert f"'{query}'" not in neg
    assert "unapproved source photos stay absent" in source
    assert "merchant_clickouts:0" in source
    assert 'a[href*="/api/clickout/"]' in source


def test_compact_search_script_parses_before_a_long_browser_run() -> None:
    node = shutil.which("node")
    assert node is not None, "Standard GitHub Actions runner must have Node installed"
    result = subprocess.run(
        [node, "--check", str(SCRIPT)],
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
