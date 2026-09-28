"""Keep true-3D brand outreach prepared, explicit and unsent."""

from pathlib import Path

PACKET = Path("examples/retail/data/dufynd_model3d_asset_requests_send_ready.md")


def test_model3d_outreach_packet_remains_prepared_not_sent() -> None:
    source = PACKET.read_text(encoding="utf-8")

    assert "Status: prepared_not_sent" in source
    assert "Nothing in this file has been sent." in source
    assert "USER_APPROVAL_REQUIRED before outbound sending" in source


def test_model3d_outreach_covers_priority_exact_variants() -> None:
    source = PACKET.read_text(encoding="utf-8")

    for product_id in (
        "SC-XERJOFF-NAXOS-100",
        "SC-YSL-LIBRE-EDP-90",
        "SC-JPG-LE-MALE-ELIXIR-PARFUM-125",
        "SC-SOSPIRO-VIBRATO-100",
        "SC-WIDIAN-LONDON-EXTRAIT-50",
    ):
        assert product_id in source


def test_model3d_outreach_requests_pipeline_rights_fields() -> None:
    source = PACKET.read_text(encoding="utf-8")

    assert "commercial use is allowed" in source
    assert "public distribution/display on DUFYND is allowed" in source
    assert "interactive web display is allowed" in source
    assert "Final geometry and visual fidelity approval remains human-only" in source
    assert "true 3D candidate queue must remain unchanged" in source
