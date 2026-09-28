from __future__ import annotations

from pathlib import Path

PACKET = Path("examples/retail/data/dufynd_release01_image_rights_request_packet.md")

OPEN_RELEASE01_IMAGE_PRODUCTS = {
    "SC-PDM-DELINA-EDP-75": "3700578501998",
    "SC-DIOR-HYPNOTIC-POISON-EDT-100": "3348900425309",
    "SC-YSL-BLACK-OPIUM-EDP-90": "3365440787971",
    "SC-YSL-LIBRE-EDP-90": "3614272648425",
}


def test_release01_rights_request_packet_covers_all_open_image_products() -> None:
    text = PACKET.read_text(encoding="utf-8")

    for product_id, gtin in OPEN_RELEASE01_IMAGE_PRODUCTS.items():
        assert product_id in text
        assert gtin in text


def test_release01_rights_request_packet_cannot_be_mistaken_for_permission() -> None:
    text = PACKET.read_text(encoding="utf-8")

    assert "prepared_not_sent" in text
    assert "USER_APPROVAL_REQUIRED" in text
    assert "No outbound request may be sent" in text
    assert "It does not approve the visual asset automatically" in text
    assert "commercial public web use explicitly allowed" in text
