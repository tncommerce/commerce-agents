from __future__ import annotations

import json
from pathlib import Path

from scripts.render_scentai_pilot_previews import (
    SCENE_PRODUCTS_BATCH01,
    SCENE_PRODUCTS_BATCH02,
    SCENE_PRODUCTS_BATCH03,
)

DATA_DIR = Path("examples/retail/data")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def assert_scene_map_matches_manifest(
    manifest_name: str,
    scene_map: dict[str, list[list[str]]],
) -> None:
    manifest = load_json(DATA_DIR / manifest_name)
    pilots = manifest.get("pilots", [])

    manifest_ids = {
        str(pilot["content_id"])
        for pilot in pilots
    }
    assert set(scene_map) == manifest_ids

    for pilot in pilots:
        content_id = str(pilot["content_id"])
        scenes = pilot.get("scenes", [])
        mapped = scene_map[content_id]

        assert len(mapped) == len(scenes)
        assert all(product_ids for product_ids in mapped)


def test_batch01_scene_map_matches_manifest() -> None:
    assert_scene_map_matches_manifest(
        "scentai_pilot_batch_01.json",
        SCENE_PRODUCTS_BATCH01,
    )


def test_batch02_scene_map_matches_manifest() -> None:
    assert_scene_map_matches_manifest(
        "scentai_pilot_batch_02.json",
        SCENE_PRODUCTS_BATCH02,
    )


def test_batch03_scene_map_matches_manifest() -> None:
    assert_scene_map_matches_manifest(
        "scentai_pilot_batch_03.json",
        SCENE_PRODUCTS_BATCH03,
    )
