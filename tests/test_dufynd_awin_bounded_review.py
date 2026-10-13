from __future__ import annotations

import base64
import csv
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from scripts import export_dufynd_awin_review as review
from tests.test_dufynd_awin_four_row_export import decrypt

NOW = datetime(2026, 10, 13, 12, tzinfo=UTC)
SECRET = "DO_NOT_EXPORT_SECRET_123"


def metadata():
    return {
        "source": "awin_product_feed_list",
        "advertiser_id": "31081",
        "feed_id": "91379",
        "checked_at": NOW.isoformat(),
        "joined": True,
        "downloaded": True,
        "download_url": "https://invalid.test/apikey/" + SECRET,
    }


def rights():
    return json.loads(
        Path("examples/retail/data/dufynd_affiliate_feed_image_rights.json").read_text()
    )


def rows():
    return [
        {
            "merchant_product_id": sku or str(910000 + i),
            "product_name": f"{brand} {name} {concentration} {size} ml",
            "search_price": "100.00",
            "currency": "EUR",
            "in_stock": "true",
            "merchant_deep_link": "https://www.topparfuemerie.de/test-product?sku="
            + (sku or str(910000 + i)),
            "aw_deep_link": "https://www.awin1.com/pclick.php?p=123456&a=3099222&m=31081",
            "description": SECRET,
        }
        for i, (_, brand, name, concentration, size, sku) in enumerate(review.TARGETS)
    ]


def build(source=None, meta=None, registry=None):
    return review.build_review(
        rows() if source is None else source,
        metadata() if meta is None else meta,
        rights() if registry is None else registry,
        SECRET,
        now=NOW,
    )


def test_fixed_five_exact_matches_are_evidence_not_approvals():
    report = build(rows() + [{"merchant_product_id": "999999", "product_name": SECRET}])
    assert len(report["results"]) == 5
    assert all(x["status"] == "EXACT_VARIANT_REVIEW_REQUIRED" for x in report["results"])
    assert all(
        not x["activation_allowed"]
        and not x["image_registration_allowed"]
        and not x["tracking_verified"]
        for x in report["results"]
    )
    assert not report["activation_allowed"] and not report["tracking_verified"]
    assert SECRET not in json.dumps(report) and "download_url" not in json.dumps(report)
    assert "999999" not in json.dumps(report)
    assert report["results"][0]["evidence"]["fields"]["merchant_deep_link"].endswith("sku=707368")
    assert hashlib.sha256(json.dumps(review.TARGETS).encode()).hexdigest() == review.MANIFEST_SHA256


@pytest.mark.parametrize("index", range(5))
@pytest.mark.parametrize("mutation", ["wrong_strength", "wrong_size", "exclusif", "extrait", "set"])
def test_variant_confusion_never_becomes_exact(index, mutation):
    source = rows()
    row = source[index]
    if mutation == "wrong_strength":
        row["product_name"] = row["product_name"].replace(
            review.TARGETS[index][3], "Eau de Cologne"
        )
    elif mutation == "wrong_size":
        row["product_name"] = row["product_name"].replace(
            str(review.TARGETS[index][4]) + " ml", "30 ml"
        )
    else:
        row["product_name"] += " " + mutation
    item = build(source)["results"][index]
    assert item["status"] in {"UNKNOWN", "HOLD_IDENTITY_CONFLICT"}
    assert "evidence" not in item and not item["absence_proven"]


@pytest.mark.parametrize("index", range(5))
def test_duplicate_sku_counts_even_unsafe_or_conflicting_rows(index):
    source = rows()
    duplicate = {
        "merchant_product_id": source[index]["merchant_product_id"],
        "product_name": "Unrelated WRONG variant",
        "merchant_image_url": "javascript:bad",
    }
    for ordered in (source + [duplicate], [duplicate] + source):
        item = build(ordered)["results"][index]
        assert item["status"] in {"HOLD_AMBIGUOUS", "HOLD_AMBIGUOUS_SKU"}
        assert "evidence" not in item


def test_two_unknown_skus_matching_same_identity_hold_without_export():
    source = rows()
    source.append({**source[4], "merchant_product_id": "919999"})
    assert build(source)["results"][4]["status"] == "HOLD_AMBIGUOUS"


def test_no_rows_means_unknown_not_absence():
    assert all(x["status"] == "UNKNOWN" and not x["absence_proven"] for x in build([])["results"])


@pytest.mark.parametrize(
    "field,value",
    [("size", "50 ml"), ("size", "100"), ("volume", "secret"), ("product_size", "100 ml + 10 ml")],
)
def test_conflicting_or_unparseable_size_remains_hold(field, value):
    source = rows()
    source[0][field] = value
    assert build(source)["results"][0]["status"] == "HOLD_SIZE_UNVERIFIED"


def test_size_missing_does_not_derive_from_sku_or_image():
    source = rows()
    source[0]["product_name"] = "Rabanne 1 Million EDT"
    source[0]["merchant_image_url"] = (
        "https://www.topparfuemerie.de/media/catalog/product/7/0/707368_3349666007921_051.png"
    )
    item = build(source)["results"][0]
    assert item["status"] == "HOLD_SIZE_UNVERIFIED"
    assert "gtin" not in item["evidence"]["fields"]
    source[0]["size"] = "100 ml"
    assert build(source)["results"][0]["status"] == "EXACT_VARIANT_REVIEW_REQUIRED"


@pytest.mark.parametrize(
    "change",
    [
        {"joined": False},
        {"downloaded": False},
        {"advertiser_id": "999"},
        {"feed_id": "999"},
        {"checked_at": (NOW - timedelta(hours=2)).isoformat()},
        {"checked_at": (NOW + timedelta(seconds=1)).isoformat()},
        {"checked_at": "2026-10-13T12:00:00"},
    ],
)
def test_invalid_source_fails_closed(change):
    with pytest.raises(ValueError):
        build(meta={**metadata(), **change})


def test_rights_registry_is_required_not_a_publication_permission():
    for reg in ({"status": "active", "entries": []}, {**rights(), "status": "inactive"}):
        with pytest.raises(ValueError):
            build(registry=reg)


@pytest.mark.parametrize(
    "value", [SECRET, base64.b64encode(SECRET.encode()).decode(), SECRET.encode().hex()]
)
def test_secrets_and_foreign_tracking_are_withheld(value):
    source = rows()
    source[0]["currency"] = value
    source[0]["aw_deep_link"] = "https://www.awin1.com/pclick.php?p=123&a=999&m=31081"
    source[0]["merchant_deep_link"] = "https://www.topparfuemerie.de/test?token=" + value
    result = build(source)
    encoded = json.dumps(result)
    assert SECRET not in encoded and value not in encoded
    assert set(result["results"][0]["evidence"]["withheld_fields"]) == {
        "currency",
        "aw_deep_link",
        "merchant_deep_link",
    }


def test_atomic_ciphertext_no_clobber_and_concurrent_attempts(tmp_path):
    target = tmp_path / "evidence.json"

    def attempt(i):
        try:
            review.atomic_encrypted_write(target, str(i).encode())
            return True
        except FileExistsError:
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(attempt, range(8))) == 1
    assert target.read_bytes() in [str(i).encode() for i in range(8)]
    assert list(tmp_path.iterdir()) == [target]


def test_interrupted_atomic_write_leaves_no_final_then_restart_works(tmp_path, monkeypatch):
    target = tmp_path / "evidence.json"
    with monkeypatch.context() as m:
        m.setattr(review.os, "fsync", lambda fd: (_ for _ in ()).throw(KeyboardInterrupt()))
        with pytest.raises(KeyboardInterrupt):
            review.atomic_encrypted_write(target, b"encrypted")
    assert not list(tmp_path.iterdir())
    review.atomic_encrypted_write(target, b"complete")
    assert target.read_bytes() == b"complete"


def test_cli_missing_secret_does_not_download_or_echo_arguments(tmp_path):
    run = subprocess.run(
        [
            sys.executable,
            "scripts/export_dufynd_awin_review.py",
            "--recipient",
            ".github/dufynd-awin-evidence-recipient.pub",
            "--output",
            str(tmp_path / "result"),
        ],
        env={**os.environ, "AWIN_DATA_FEED_API_KEY": ""},
        capture_output=True,
        text=True,
    )
    assert run.returncode == 2 and run.stderr.strip() == "bounded_feed_review_failed_closed"
    assert not list(tmp_path.iterdir())


def test_actual_acquisition_path_encrypts_only_five_and_cleans_raw(tmp_path, monkeypatch):
    private = X25519PrivateKey.generate()
    public = private.public_key().public_bytes_raw()
    recipient = tmp_path / "recipient"
    recipient.write_text(public.hex())
    monkeypatch.setattr(review, "RECIPIENT_SHA256", hashlib.sha256(public).hexdigest())
    monkeypatch.setenv("AWIN_DATA_FEED_API_KEY", SECRET)
    work_paths = []

    def acquire(**kwargs):
        assert kwargs["advertiser_id"] == "31081" and kwargs["feed_id"] == "91379"
        assert kwargs["report_path"] is None
        work_paths.append(kwargs["output_path"].parent)
        source = rows()
        with kwargs["output_path"].open("w") as f:
            writer = csv.DictWriter(f, fieldnames=list(source[0]))
            writer.writeheader()
            writer.writerows(source)
        return {**metadata(), "checked_at": datetime.now(UTC).isoformat()}

    monkeypatch.setattr(review, "download_feed_from_list", acquire)
    output = tmp_path / "result.encrypted.json"
    review.run_review(recipient, output)
    decoded = decrypt(output.read_bytes(), private)
    assert len(decoded["results"]) == 5 and len(decoded["source"]["feed_sha256"]) == 64
    assert not any(p.exists() for p in work_paths)
    assert SECRET.encode() not in output.read_bytes() and b"Rabanne" not in output.read_bytes()
    assert output.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("failure", [KeyboardInterrupt, RuntimeError])
def test_download_interruption_cleans_partial_plaintext_and_logs_no_secret(
    tmp_path, monkeypatch, capsys, failure
):
    work_paths = []

    def acquire(**kwargs):
        work_paths.append(kwargs["output_path"].parent)
        kwargs["output_path"].write_text(SECRET)
        raise failure(SECRET)

    monkeypatch.setenv("AWIN_DATA_FEED_API_KEY", SECRET)
    monkeypatch.setattr(review, "download_feed_from_list", acquire)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "review",
            "--recipient",
            ".github/dufynd-awin-evidence-recipient.pub",
            "--output",
            str(tmp_path / "result"),
        ],
    )
    assert review.main() == 2
    assert not any(p.exists() for p in work_paths) and not (tmp_path / "result").exists()
    captured = capsys.readouterr()
    assert (
        captured.err.strip() == "bounded_feed_review_failed_closed"
        and SECRET not in captured.out + captured.err
    )


def test_recipient_drift_stops_before_fetch(tmp_path, monkeypatch):
    recipient = tmp_path / "wrong"
    recipient.write_text("00" * 32)
    monkeypatch.setenv("AWIN_DATA_FEED_API_KEY", SECRET)
    monkeypatch.setattr(
        review, "download_feed_from_list", lambda **kwargs: pytest.fail("must not fetch")
    )
    with pytest.raises(ValueError, match="recipient_drift"):
        review.run_review(recipient, tmp_path / "result")


def test_workflow_profile_is_manual_isolated_and_ciphertext_only():
    text = Path(".github/workflows/dufynd-awin-feed-revalidation.yml").read_text()
    bounded = text.split("  bounded-private-review:", 1)[1].split(
        "  revalidate-top-parfuemerie:", 1
    )[0]
    assert "github.event_name == 'workflow_dispatch'" in bounded
    assert "github.ref == 'refs/heads/dufynd-feed-05-20261013'" in bounded
    assert "timeout-minutes: 10" in bounded and "cancel-in-progress: false" in bounded
    assert "retention-days: 1" in bounded and "persist-credentials: false" in bounded
    assert "umask 077" in bounded and "trap" in bounded
    assert "top-parfuemerie.csv" not in bounded and "release01" not in bounded
    assert "path: ${{ runner.temp }}/bounded-review.encrypted.json" in bounded
    assert "python scripts/export_dufynd_awin_review.py" in bounded
