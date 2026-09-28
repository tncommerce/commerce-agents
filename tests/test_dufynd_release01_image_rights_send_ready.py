from pathlib import Path

PACKET = Path("examples/retail/data/dufynd_release01_image_rights_send_ready.md")

PRODUCTS = {
    "SC-PDM-DELINA-EDP-75": "3700578501998",
    "SC-DIOR-HYPNOTIC-POISON-EDT-100": "3348900425309",
    "SC-YSL-BLACK-OPIUM-EDP-90": "3365440787971",
    "SC-YSL-LIBRE-EDP-90": "3614272648425",
}


def test_send_ready_packet_tracks_partial_send_state() -> None:
    source = PACKET.read_text(encoding="utf-8")

    assert "Status: partially_sent" in source
    assert "Status: sent_2026-09-28_after_explicit_user_approval" in source
    assert "Recipient: contact@dior.com" in source
    assert "USER_APPROVAL_REQUIRED before any outbound message" in source
    assert (
        "No remaining outbound message in this file may be sent without explicit user approval."
        in source
    )


def test_send_ready_packet_covers_all_four_release01_products() -> None:
    source = PACKET.read_text(encoding="utf-8")

    for gtin in PRODUCTS.values():
        assert gtin in source

    assert "Parfums de Marly — Delina" in source
    assert "Dior — Hypnotic Poison" in source
    assert "Yves Saint Laurent — Black Opium" in source
    assert "Yves Saint Laurent — Libre" in source


def test_send_ready_packet_preserves_rights_and_visual_approval_separation() -> None:
    source = PACKET.read_text(encoding="utf-8")

    assert "human visual approval remains separate" in source
    assert "licensed_source_required" in source
    assert "register the exact asset as a review-only rights-cleared candidate" in source
