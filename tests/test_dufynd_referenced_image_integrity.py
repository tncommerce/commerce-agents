from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

DATA_DIR = Path("examples/retail/data")
PUBLIC_DIR = Path("examples/retail/storefront-web/public")

IMAGE_MANIFESTS = (
    DATA_DIR / "catalog.json",
    DATA_DIR / "scentai_products.json",
    DATA_DIR / "scentai_launch_production_pack_01.json",
    DATA_DIR / "scentai_launch_production_pack_02.json",
    DATA_DIR / "scentai_launch_production_pack_03.json",
)

IMAGE_FIELDS = {"image_url", "product_cutout_url"}


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def collect_local_product_images(value: object) -> set[str]:
    refs: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return

        if not isinstance(node, dict):
            return

        for key, item in node.items():
            if (
                key in IMAGE_FIELDS
                and isinstance(item, str)
                and item.startswith("/products/")
            ):
                refs.add(item)
            walk(item)

    walk(value)
    return refs


def test_all_referenced_local_product_images_exist_and_decode() -> None:
    image_refs: set[str] = set()
    for manifest_path in IMAGE_MANIFESTS:
        image_refs.update(collect_local_product_images(load_json(manifest_path)))

    assert image_refs, "Expected at least one referenced local product image"

    failures: list[str] = []
    for image_ref in sorted(image_refs):
        image_path = PUBLIC_DIR / image_ref.lstrip("/")
        if not image_path.is_file():
            failures.append(f"{image_ref}: missing file")
            continue

        try:
            with Image.open(image_path) as image:
                image.load()
                if image.width <= 0 or image.height <= 0:
                    failures.append(
                        f"{image_ref}: invalid dimensions {image.width}x{image.height}"
                    )
        except Exception as exc:
            failures.append(
                f"{image_ref}: image decode failed ({type(exc).__name__}: {exc})"
            )

    assert not failures, "Broken referenced product assets:\n" + "\n".join(failures)
