from pathlib import Path

ASSET = (
    Path(__file__).resolve().parents[1]
    / "examples/retail/storefront-web/public/products/pilot/xerjoff-naxos-campaign-master.webp"
)


def test_naxos_campaign_master_webp_is_complete() -> None:
    data = ASSET.read_bytes()

    assert data[:4] == b"RIFF"
    assert data[8:12] == b"WEBP"

    declared_file_size = int.from_bytes(data[4:8], "little") + 8
    assert declared_file_size == len(data)
