"""Guard public growth regression against fixed 37 baseline after 20-profile release."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path("examples/retail")
SOURCE = ROOT / "storefront-web/scripts/test-catalog-growth.mjs"
DATA = ROOT / "data"


def test_growth_qa_preserves_public_authorization_and_wave_two_hold() -> None:
    content = SOURCE.read_text(encoding="utf-8")
    assert "const originallyPublic=data.canonical.filter" in content
    assert "publishedApprovals=approvals.filter" in content
    assert "a.publication_approved===true&&a.indexing_approved===true" in content
    assert "exactPublicIds" in content
    assert "waveTwo.public_release_authorized,false" in content
    assert "held second wave was counted as published" in content
    assert "result.counts.existing_public,exactPublicIds.size" in content
    assert "Math.max(0,target-exactPublicIds.size)" in content
    assert "assert.equal(result.counts.existing_public,37)" not in content
    assert "[13,38,63,64]" not in content

    approvals = json.loads(
        (DATA / "dufynd_release_authorizations.json").read_text(encoding="utf-8")
    )["approvals"]
    released = [
        x["product_id"]
        for x in approvals
        if x["publication_approved"] is True and x["indexing_approved"] is True
    ]
    held = json.loads((DATA / "dufynd_facts_wave_02_review.json").read_text(encoding="utf-8"))
    assert len(released) == 20
    assert held["public_release_authorized"] is False
    assert not set(released).intersection(p["product_id"] for p in held["profiles"])


def test_catalog_growth_qa_has_valid_node_syntax() -> None:
    node = shutil.which("node")
    assert node is not None
    test = subprocess.run(
        [node, "--check", str(SOURCE)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert test.returncode == 0, test.stdout + test.stderr
