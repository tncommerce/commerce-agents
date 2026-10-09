"""Keep the staged fidelity packet bound to exact variants and private bytes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

DATA = Path("examples/retail/data")
CANDIDATE_DIR = Path("examples/retail/review-assets/catalog-candidates")
PUBLIC_ROOT = Path("examples/retail/storefront-web/public")
PACKET = DATA / "dufynd_staged_image_fidelity_candidates_20260930.json"


def test_staged_candidate_files_match_reviewed_bytes_and_exact_variants() -> None:
    packet = json.loads(PACKET.read_text())
    staging = json.loads((DATA / "scentai_catalog_staging.json").read_text())
    products = {row["product_id"]: row for row in staging["products"]}
    items = packet["items"]
    paths = {Path(item["candidate_asset"]) for item in items}
    assert len(paths) == len(items)
    assert len({item["product_id"] for item in items}) == len(items)
    assert paths == {path for path in CANDIDATE_DIR.rglob("*") if path.is_file()}

    for item in items:
        product = products[item["product_id"]]
        assert item["concentration"] == product["concentration"]
        assert item["volume_ml"] == product["volume_ml"]
        path = Path(item["candidate_asset"])
        assert path.is_relative_to(CANDIDATE_DIR)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
        with Image.open(path) as image:
            assert image.size == (item["width"], item["height"])
            assert min(image.size) >= 1000
            assert "A" in image.getbands()
            low, high = image.getchannel("A").getextrema()
            assert low == 0 and high == 255
        assert item["has_alpha"] is True


def test_staged_candidates_have_no_public_copy_or_catalog_activation() -> None:
    packet = json.loads(PACKET.read_text())
    assert all(value is False for value in packet["approval_scope"].values())
    public_files = [path for path in PUBLIC_ROOT.rglob("*") if path.is_file()]
    public_hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in public_files}
    public_names = {path.name for path in public_files}
    catalogs = [
        json.loads((DATA / filename).read_text())
        for filename in ("scentai_products.json", "catalog.json")
    ]
    staging = json.loads((DATA / "scentai_catalog_staging.json").read_text())
    staged = {row["product_id"]: row for row in staging["products"]}

    expected_status = {
        "SC-YSL-LIBRE-EDP-90": "human_fidelity_approved_pending_registration",
        "SC-GUERLAIN-MON-GUERLAIN-EDP-100": "pending_human_fidelity",
        "SC-JPG-LE-MALE-ELIXIR-PARFUM-125": "pending_human_fidelity",
    }

    for item in packet["items"]:
        assert item["status"] == expected_status[item["product_id"]]
        assert item["source_registration_status"] == "not_registered"
        assert item["reference_only"] is True
        assert item["catalog_promotion"] is False
        assert item["public_activation"] is False
        assert item["sha256"] not in public_hashes
        assert Path(item["candidate_asset"]).name not in public_names
        for catalog in catalogs:
            live = next(
                (row for row in catalog["products"] if row["product_id"] == item["product_id"]),
                None,
            )
            if item["product_id"] == "SC-YSL-LIBRE-EDP-90":
                # Only the independently approved merchant photograph is live.
                assert live is not None
                assert live["image_url"] == staged[item["product_id"]]["media"]["image_url"]
                assert Path(item["candidate_asset"]).name not in json.dumps(live)
            else:
                assert live is None
        product = staged[item["product_id"]]
        if item["product_id"] == "SC-YSL-LIBRE-EDP-90":
            assert product["media"]["image_url"] == (
                "https://www.topparfuemerie.de/media/catalog/product/8/5/"
                "856448_3614272648425_051.png"
            )
            assert product["media"]["image_status"] == "approved_feed_image"
        else:
            assert product["media"]["image_url"] is None
        assert product["validation"]["catalog_ready"] is False
        if item["product_id"] == "SC-YSL-LIBRE-EDP-90":
            # The merchant-feed image was separately approved on 2026-10-01;
            # approval of an internal generated candidate is still prohibited.
            assert "approved_product_image_pending" not in product["validation"]["blockers"]
            assert product["validation"]["blockers"] == ["verified_purchase_destination_pending"]
        else:
            assert "approved_product_image_pending" in product["validation"]["blockers"]

    libre = next(item for item in packet["items"] if item["product_id"] == "SC-YSL-LIBRE-EDP-90")
    assert libre["approval_basis"] == "explicit_user_visual_approval_2026-09-30"
    assert libre["approved_at"] == "2026-09-30"
