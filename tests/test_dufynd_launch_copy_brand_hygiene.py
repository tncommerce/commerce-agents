from __future__ import annotations

from pathlib import Path

LAUNCH_COPY_FILES = (
    Path("examples/retail/data/scentai_launch_content_plan.json"),
    Path("examples/retail/data/scentai_launch_production_pack_01.json"),
    Path("examples/retail/data/scentai_launch_production_pack_02.json"),
    Path("examples/retail/data/scentai_launch_production_pack_03.json"),
    Path("examples/retail/data/scentai_launch_scripts_batch_01.json"),
    Path("examples/retail/data/scentai_launch_scripts_batch_02.json"),
    Path("examples/retail/data/scentai_launch_scripts_batch_03.json"),
)


def test_launch_copy_uses_current_public_dufynd_brand() -> None:
    for path in LAUNCH_COPY_FILES:
        content = path.read_text(encoding="utf-8-sig")

        assert "SCENTAI" not in content, path
        assert "#scentai" not in content.casefold(), path
        assert "DUFYND" in content, path


def test_legacy_internal_file_and_format_ids_can_remain_scentai_named() -> None:
    content_plan = LAUNCH_COPY_FILES[0].read_text(encoding="utf-8-sig")
    batch03 = LAUNCH_COPY_FILES[-1].read_text(encoding="utf-8-sig")

    assert "scentai_decides" in content_plan
    assert "scentai_decides" in batch03
