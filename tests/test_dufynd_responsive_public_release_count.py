"""Responsive QA must count source and authorized public release, never 37 forever."""

import json
import shutil
import subprocess
from pathlib import Path

SOURCE = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")


def test_responsive_sweep_binds_both_gated_public_catalog_cohorts() -> None:
    content = SOURCE.read_text(encoding="utf-8")
    assert "released-profiles.json" in content
    assert "dufynd_release_authorizations.json" in content
    assert "const sourceQualifiedProducts =" in content
    assert "const publishedRoutes = [" in content
    assert "const expectedFragranceCount = publishedRoutes.length;" in content
    assert "sourceQualifiedRoutes" in content
    assert "approvedProductIds.has(p.product_id)" in content
    assert "p.indexing_approved !== true" in content
    assert "new Set(publishedRoutes).size !== publishedRoutes.length" in content
    assert "const expectedFragranceCount = sourceCatalog.products.filter(" not in content


def test_audience_qa_counts_and_routes_include_released_profiles() -> None:
    content = SOURCE.read_text(encoding="utf-8")
    assert "function audienceForGroups(values)" in content
    assert "sourceQualifiedProducts" in content
    assert "releasedProfiles" in content
    assert "audienceForGroups(row.target_groups) === audience" in content
    assert "row.seo.public_path" in content
    assert "if (seenAudienceByRoute.size !== expectedFragranceCount)" in content
    assert "if (detailRoutes.length !== expectedFragranceCount)" in content
    assert "catalog sweep expected" in content
    assert "source-blocked fragrances leaked" in content


def test_exact_public_57_snapshot_and_held_second_wave() -> None:
    data = Path("examples/retail/data")
    src = json.loads((data / "scentai_products.json").read_text(encoding="utf-8"))
    released = json.loads(
        Path("examples/retail/storefront-web/lib/generated/released-profiles.json").read_text(
            encoding="utf-8"
        )
    )["profiles"]
    approvals = json.loads(
        (data / "dufynd_release_authorizations.json").read_text(encoding="utf-8")
    )["approvals"]
    private_wave = json.loads((data / "dufynd_facts_wave_02_review.json").read_text(
        encoding="utf-8"
    ))["profiles"]
    qualified = [
        row for row in src["products"]
        if str(row.get("product_id", "")).startswith("SC-")
        and not any(str(x).strip() for x in row.get("validation", {}).get("blockers", []))
    ]
    assert len(qualified) == 37
    assert len(released) == len(approvals) == 20
    assert len(qualified) + len(released) == 57
    authorized = {
        p["product_id"] for p in approvals
        if p["publication_approved"] is True and p["indexing_approved"] is True
    }
    assert authorized == {p["product_id"] for p in released}
    assert not authorized.intersection(p["product_id"] for p in private_wave)


def test_visual_browser_script_is_valid_node_syntax_without_network() -> None:
    node = shutil.which("node")
    assert node is not None, "Node must be available on standard GitHub runner"
    checked = subprocess.run(
        [node, "--check", str(SOURCE)],
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
