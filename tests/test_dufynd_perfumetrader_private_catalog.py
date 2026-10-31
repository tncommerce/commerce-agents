from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from scripts import review_dufynd_perfumetrader_catalog as review

SECRET = "private-test-reader-key"
NOW = datetime(2026, 10, 31, 12, tzinfo=UTC)
PRODUCT = {
    "product_id": "SC-RABANNE-1-MILLION-EDT-100",
    "brand": "Rabanne",
    "name": "1 Million",
    "concentration": "Eau de Toilette",
    "volume_ml": 100,
}
MAPPING = {"mappings": [{"product_id": PRODUCT["product_id"], "gtin": "3349666007921"}]}
META = {
    "advertiser_id": "11672",
    "feed_id": "29975",
    "joined": True,
    "primary_region": "DE",
    "language": "German",
    "last_imported": "2026-10-27 16:02:27",
}


def source_row(**changes):
    row = {
        "product_name": "Rabanne 1 Million Eau de Toilette 100 ml",
        "merchant_product_id": "12345",
        "ean": "3349666007921",
        "search_price": "59.99",
        "currency": "EUR",
        "in_stock": "1",
        "is_for_sale": "1",
        "delivery_cost": "4.95",
        "delivery_country": "DE",
        "last_updated": "2026-10-31T10:00:00Z",
        "aw_deep_link": "https://www.awin1.com/pclick.php?p=12345&a=3099222&m=11672",
    }
    return row | changes


def result(*rows):
    return review.review_rows([PRODUCT], MAPPING, list(rows), META, SECRET, NOW)["profiles"][0]


def test_exact_fresh_source_still_never_activates_or_approves_assets():
    value = result(source_row())
    assert value["status"] == "EXACT_AND_FRESH"
    assert value["offer_activation_allowed"] is False
    assert value["image_publication_allowed"] is False
    assert value["candidates"][0]["tracking_click_verified"] is False


@pytest.mark.parametrize(
    "changed",
    [
        {"last_updated": "2026-10-31 10:00:00"},
        {"in_stock": ""},
        {"delivery_country": ""},
        {"search_price": "NaN"},
        {"delivery_cost": "-1"},
        {"stock_quantity": "0"},
        {"stock_quantity": "0.0"},
        {"stock_quantity": "00"},
        {"stock_quantity": "-1"},
        {"is_for_sale": "0"},
        {"is_for_sale": ""},
        {"shipping_cost": "9.95"},
        {"shipping_country": "AT"},
        {"size": "200"},
        {"product_size": "200"},
        {"last_update": "2026-10-25T10:00:00Z"},
        {"aw_deep_link": "https://www.awin1.com/pclick.php?p=12345&a=999&m=11672"},
    ],
)
def test_missing_or_contradictory_commerce_evidence_is_hold(changed):
    assert result(source_row(**changed))["status"] == "EXACT_BUT_INCOMPLETE"


def test_old_product_time_is_stale_and_feed_import_time_cannot_refresh_it():
    value = result(source_row(last_updated="2026-10-27T10:00:00Z"))
    assert value["status"] == "STALE"
    assert value["candidates"][0]["original_product_timestamp"] == "2026-10-27T10:00:00Z"
    value = result(source_row(last_updated=""))
    assert value["status"] == "EXACT_BUT_INCOMPLETE"
    assert value["candidates"][0]["original_product_timestamp_utc"] is None


@pytest.mark.parametrize(
    "title",
    [
        "Rabanne 1 Million Eau de Parfum 100 ml",
        "Rabanne 1 Million Eau de Toilette 200 ml",
        "Rabanne 1 Million Elixir Eau de Toilette 100 ml",
        "Rabanne 1 Million Eau de Toilette 100 ml Refill",
    ],
)
def test_exact_gtin_never_overrides_variant_mismatch(title):
    assert result(source_row(product_name=title))["status"] == "MISMATCH"


def test_explicit_size_and_gtin_conflicts_do_not_pass_exact_title():
    assert result(source_row(size="200 ml"))["status"] == "MISMATCH"
    assert result(source_row(gtin="3614272648425"))["status"] == "MISMATCH"


def test_duplicate_exact_rows_block_and_output_is_bounded():
    value = result(*(source_row(merchant_product_id=str(i)) for i in range(8)))
    assert value["status"] == "BLOCKED"
    assert len(value["candidates"]) == 3
    assert value["candidate_count"] == 8
    assert result()["status"] == "NOT_FOUND"


def test_secret_bearing_or_external_urls_and_nonallowlisted_columns_never_export():
    row = source_row(
        merchant_deep_link="https://www.perfumetrader.de/product?token=" + quote(SECRET),
        merchant_image_url="https://evil.example/packshot.png",
        customer_email="private@example.com",
        specifications=base64.b64encode(SECRET.encode()).decode(),
    )
    fields, withheld = review.safe_fields(row, SECRET)
    assert "customer_email" not in fields
    assert set(withheld) == {"merchant_deep_link", "merchant_image_url", "specifications"}
    assert SECRET not in json.dumps(fields)
    assert not review.safe_url(
        "https://www.awin1.com/cread.php?awinaffid=3099222&awinmid=11672&ued="
        + quote("https://evil.example/product", safe=""),
        "aw_deep_link",
        SECRET,
    )


def test_feed_and_public_catalog_are_scope_bound():
    with pytest.raises(ValueError, match="feed_identity"):
        review.review_rows([PRODUCT], MAPPING, [], META | {"feed_id": "94153"}, SECRET, NOW)
    assert len(review.public_profiles(json.loads(review.CATALOG.read_text()))) == 37
    with pytest.raises(ValueError, match="public_catalog_scope_changed"):
        review.public_profiles({"products": []})


def test_only_recipient_can_decrypt_evidence_and_cipher_is_authenticated():
    private = X25519PrivateKey.generate()
    recipient = private.public_key().public_bytes_raw()
    envelope = json.loads(review.encrypt_report({"private_source": "test"}, recipient))
    values = {
        k: base64.b64decode(envelope[k])
        for k in ("ephemeral_public", "salt", "nonce", "ciphertext")
    }
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=values["salt"],
        info=review.AAD + recipient + values["ephemeral_public"],
    ).derive(private.exchange(X25519PublicKey.from_public_bytes(values["ephemeral_public"])))
    assert json.loads(AESGCM(key).decrypt(values["nonce"], values["ciphertext"], review.AAD)) == {
        "private_source": "test"
    }
    with pytest.raises(InvalidTag):
        AESGCM(key).decrypt(values["nonce"], values["ciphertext"], b"wrong-feed-identity")


def test_network_exception_is_sanitized_and_raw_temporary_file_removed(
    tmp_path, monkeypatch, capsys
):
    private = X25519PrivateKey.generate()
    pub = tmp_path / "recipient.pub"
    pub.write_text(private.public_key().public_bytes_raw().hex())
    monkeypatch.setenv("AWIN_DATA_FEED_API_KEY", SECRET)
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))

    def failed_download(**kwargs):
        kwargs["output_path"].write_text("sensitive raw feed")
        raise RuntimeError("secret " + SECRET)

    monkeypatch.setattr(review, "download_feed_from_list", failed_download)
    monkeypatch.setattr(
        "sys.argv",
        ["review", "--recipient", str(pub), "--output", str(tmp_path / "encrypted.json")],
    )
    assert review.main() == 2
    assert capsys.readouterr().err == "perfumetrader_private_review_failed_closed\n"
    assert not list(tmp_path.glob("dufynd-pt-*"))
    assert not (tmp_path / "encrypted.json").exists()


def test_new_workflow_mode_cannot_run_top_or_inventory_and_uploads_ciphertext_only():
    text = Path(".github/workflows/dufynd-awin-feed-revalidation.yml").read_text()
    block = text.split("  review-perfumetrader-private-catalog:", 1)[1]
    assert "inputs.inventory_task == 'perfumetrader_private_catalog'" in block
    assert "github.ref == 'refs/heads/scentai-mvp'" in block
    assert "persist-credentials: false" in block
    assert "retention-days: 1" in block
    artifact = block.split("Upload recipient-encrypted catalog evidence only", 1)[1]
    assert "perfumetrader-catalog.encrypted.json" in artifact
    assert "source.csv" not in artifact
    assert ".github/dufynd-awin-evidence-recipient.pub" not in block
    assert "inputs.inventory_task == 'top_parfuemerie_review'" in text
    assert "inputs.inventory_task == 'perfumetrader_inventory'" in text


def test_stock_availability_never_substitutes_for_explicit_purchase_permission():
    for value in ("", "0", "false", "unknown"):
        profile = result(source_row(is_for_sale=value))
        assert profile["status"] == "EXACT_BUT_INCOMPLETE"
        row = profile["candidates"][0]
        assert row["stock_available"] is True
        assert row["source_purchase_eligible"] is False
        assert "explicit_purchase_permission_missing_or_false" in row["reasons"]
    available = result(source_row())["candidates"][0]
    assert available["source_purchase_eligible"] is True
    assert result(source_row(in_stock="0"))["candidates"][0]["source_purchase_eligible"] is False


def test_equivalent_shipping_aliases_do_not_create_false_conflicts():
    assert (
        result(source_row(shipping_cost="4.950", shipping_country="Germany"))["status"]
        == "EXACT_AND_FRESH"
    )
