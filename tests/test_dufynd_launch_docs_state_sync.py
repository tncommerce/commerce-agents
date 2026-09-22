from __future__ import annotations

from pathlib import Path

LAUNCH_DOCS = (
    Path("examples/retail/data/scentai_launch_readiness.md"),
    Path("examples/retail/data/scentai_growth_launch_plan.md"),
    Path("examples/retail/data/scentai_launch_attribution.md"),
    Path("examples/retail/data/scentai_launch_measurement_status.md"),
)


def test_launch_docs_use_current_public_brand_name() -> None:
    for path in LAUNCH_DOCS:
        content = path.read_text(encoding="utf-8-sig")

        assert "SCENTAI" not in content, path
        assert "DUFYND" in content, path


def test_launch_readiness_records_observed_live_seo_state_without_auto_change() -> None:
    content = LAUNCH_DOCS[0].read_text(encoding="utf-8-sig")

    assert "robots.txt` currently permits search indexing" in content
    assert "no SEO environment setting was changed during this audit" in content
    assert "silently flip the value in either direction" in content
    assert "explicit operator launch/SEO decision" in content


def test_measurement_status_keeps_commerce_as_current_priority() -> None:
    content = LAUNCH_DOCS[3].read_text(encoding="utf-8-sig")

    assert "Commerce readiness" in content
    assert "Perfumetrader/Awin product feed" in content
    assert "explicit publishing approval" in content
