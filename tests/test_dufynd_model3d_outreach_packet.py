"""Keep dispatched true-3D outreach traceable without implying asset approval."""

from pathlib import Path

PACKET = Path("examples/retail/data/dufynd_model3d_asset_requests_send_ready.md")


def test_model3d_outreach_packet_records_dispatch_without_duplicate_sending() -> None:
    source = PACKET.read_text(encoding="utf-8")

    assert source.count("Status: sent_waiting_external") == 6
    assert "prepared_not_sent" not in source
    assert "Nothing in this file has been sent." not in source
    assert "Do not resend the prepared messages below." in source
    for message_id in (
        "1a0ef106235a24b9",
        "1a0ef1069d0f3753",
        "1a0ef106f6e313c1",
        "1a0ef107470ef598",
        "1a0ef108a890817a",
    ):
        assert message_id in source
    assert "Neither acknowledgement supplies a model" in source
    assert "concentration identity remains unresolved" in source


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
