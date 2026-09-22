from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path("examples/retail/data/dufynd_awin_top_parfuemerie_feed_intake.json")


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))


def test_top_parfuemerie_awin_intake_tracks_approved_feed_without_premature_mapping() -> None:
    config = load_config()

    assert config["status"] == "approved_product_feed_available_awaiting_real_feed_export"
    assert config["merchant_scope"]["awin_advertiser_id"] == "31081"
    assert config["source_availability"]["awin_product_data_available"] is True
    assert config["source_availability"]["create_a_feed_expected"] is True
    assert config["feed_intake"]["field_mapping_status"] == "pending_real_feed_header"
    assert config["feed_intake"]["real_feed_preflight_required"] is True


def test_top_parfuemerie_awin_intake_keeps_release_gates_closed_until_real_data() -> None:
    config = load_config()
    safety = config["safety"]

    assert safety["no_offer_activation_before_real_feed_preflight"] is True
    assert safety["no_catalog_write_before_exact_variant_mapping"] is True
    assert safety["no_feed_image_approval_before_rights_gate"] is True
    assert safety["no_assumption_that_expected_columns_are_present"] is True
