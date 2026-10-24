"""No SKU leakage, stale prices, invented clicks or admin writes in dynamic mode."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from scripts.prepare_dufynd_runtime_offer_batch import batch_digest, prepare_batch

from retail.api import purchase_freshness, runtime_offer_snapshots
from retail.api.merchant_offers import MerchantOfferStore, offer_clickout_target

OFFER_FILE = Path("examples/retail/data/merchant_offers.json")
MIGRATION = Path("supabase/migrations/20261023221100_dufynd_runtime_offer_snapshots_v1.sql")


def canonical() -> dict:
    return next(
        item
        for item in json.loads(OFFER_FILE.read_text(encoding="utf-8"))["offers"]
        if item["offer_id"] == "notino-ysl-libre-edp-90"
    )


def snapshot(row: dict, *, now: datetime | None = None) -> dict:
    return {
        "offer_id": row["offer_id"],
        "product_id": row["product_id"],
        "merchant_id": row["merchant_id"],
        "merchant_product_id": row["merchant_product_id"],
        "identity_sha256": runtime_offer_snapshots.identity_hash(row),
        "currency": "EUR",
        "price": 119.0,
        "shipping_cost": 0.0,
        "in_stock": True,
        "verified_at": (now or datetime.now(UTC)).isoformat(),
        "decision": "verified",
        "source_type": "official_network_feed",
        "source_ref": "network:cj-fixture-allowed",
        "evidence_sha256": "a" * 64,
    }


def evidence(row: dict, *, now: datetime | None = None) -> dict:
    return {
        "schema_version": 1,
        "batch_id": "notino-batch-20261023",
        "offers": [
            {
                "offer_id": row["offer_id"],
                "product_id": row["product_id"],
                "merchant_product_id": row["merchant_product_id"],
                "variant_label": row["variant_label"],
                "brand": "Yves Saint Laurent",
                "concentration": "Eau de Parfum",
                "volume_ml": 90,
                "ean": "3614272648425",
                "price": 119.0,
                "shipping_cost": 0.0,
                "in_stock": True,
                "verified_at": (now or datetime.now(UTC)).isoformat(),
                "decision": "verified",
                "source_type": "official_network_feed",
                "source_ref": "network:cj-fixture-allowed",
                "evidence": {"source_observation": "isolated-test-fixture-no-real-feed"},
            }
        ],
    }


def test_baseline_stays_byte_for_byte_without_release_flag(monkeypatch) -> None:
    monkeypatch.delenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", raising=False)
    monkeypatch.setattr(purchase_freshness, "evidence_for", lambda _: None)
    row = canonical()
    store = MerchantOfferStore(OFFER_FILE)
    stamp = datetime.fromisoformat(row["last_updated_at"].replace("Z", "+00:00"))
    result = store.eligible_offer(row["offer_id"], now=stamp + timedelta(hours=1))
    assert result is not None
    assert result.price == row["price"]
    assert result.affiliate_url == row["affiliate_url"]


def test_one_exact_verified_batch_updates_both_list_and_clickout(monkeypatch) -> None:
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")
    row = canonical()
    fixed = snapshot(row)
    calls = []

    def read(selected):
        calls.append([offer["offer_id"] for offer in selected])
        return {row["offer_id"]: fixed}

    monkeypatch.setattr(runtime_offer_snapshots, "load_runtime_snapshots", read)
    store = MerchantOfferStore(OFFER_FILE)
    listing = store.offers_for(row["product_id"])
    click = store.eligible_offer(row["offer_id"])
    assert len(listing) == 1
    assert listing[0] == click
    assert click.price == 119
    assert click.shipping_cost == 0
    assert click.shipping_label == "Gratis Versand"
    assert click.product_url == row["product_url"]
    assert click.affiliate_url == row["affiliate_url"]
    assert offer_clickout_target(click) == row["affiliate_url"]
    all_rows = json.loads(OFFER_FILE.read_text(encoding="utf-8"))["offers"]
    expected_ids = [
        offer["offer_id"]
        for offer in all_rows
        if offer["product_id"] == row["product_id"] and offer["merchant_id"] == "notino"
    ]
    assert calls == [expected_ids, [row["offer_id"]]]


@pytest.mark.parametrize("database_result", [None, {}])
def test_no_database_observation_never_republishes_stale_file(monkeypatch, database_result) -> None:
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")
    monkeypatch.setattr(
        runtime_offer_snapshots, "load_runtime_snapshots", lambda _: database_result
    )
    row = canonical()
    store = MerchantOfferStore(OFFER_FILE)
    assert store.offers_for(row["product_id"]) == []
    assert store.eligible_offer(row["offer_id"]) is None


@pytest.mark.parametrize(
    "mutation",
    [
        {"product_id": "SC-DIFFERENT"},
        {"merchant_id": "evil"},
        {"merchant_product_id": "WRONG-SIZE"},
        {"identity_sha256": "a" * 64},
        {"decision": "hold"},
        {"source_type": "unknown-source"},
        {"evidence_sha256": "invalid"},
        {"price": 0},
        {"price": 1.234},
        {"price": -50},
        {"price": "NaN"},
        {"shipping_cost": -1},
        {"in_stock": "true"},
        {"currency": "USD"},
    ],
)
def test_mismatch_or_invalid_input_always_fails_closed(mutation) -> None:
    row = canonical()
    checked = snapshot(row)
    checked.update(mutation)
    assert runtime_offer_snapshots.apply_runtime_snapshot(row, checked) is None


@pytest.mark.parametrize("age_hours", [-1, 73])
def test_old_and_future_source_timestamps_are_not_reset(age_hours) -> None:
    row = canonical()
    now = datetime.now(UTC)
    checked = snapshot(row, now=now - timedelta(hours=age_hours))
    assert runtime_offer_snapshots.apply_runtime_snapshot(row, checked, now=now) is None


def test_hold_and_out_of_stock_are_never_eligible(monkeypatch) -> None:
    row = canonical()
    checked = snapshot(row)
    checked["in_stock"] = False
    out_of_stock = runtime_offer_snapshots.apply_runtime_snapshot(row, checked)
    assert out_of_stock is not None and out_of_stock["in_stock"] is False
    checked["decision"] = "hold"
    assert runtime_offer_snapshots.apply_runtime_snapshot(row, checked) is None
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")
    monkeypatch.setattr(
        runtime_offer_snapshots,
        "load_runtime_snapshots",
        lambda _: {row["offer_id"]: snapshot(row) | {"in_stock": False}},
    )
    assert not MerchantOfferStore(OFFER_FILE).offers_for(row["product_id"])


def test_unknown_product_never_reads_database(monkeypatch) -> None:
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")

    def forbidden(_):
        raise AssertionError("No unrelated merchant-source call is allowed")

    monkeypatch.setattr(runtime_offer_snapshots, "load_runtime_snapshots", forbidden)
    store = MerchantOfferStore(OFFER_FILE)
    assert store.offers_for("SC-NOT-RELEASED") == []
    assert store.eligible_offer("not-an-offer") is None


def test_batch_rejects_variant_change_url_change_and_duplicates() -> None:
    row = canonical()
    packet = evidence(row)
    for field, value in (
        ("merchant_product_id", "wrong"),
        ("product_id", "SC-OTHER"),
        ("variant_label", "50ml"),
        ("affiliate_url", "https://evil.invalid"),
    ):
        altered = json.loads(json.dumps(packet))
        altered["offers"][0][field] = value
        with pytest.raises(ValueError):
            prepare_batch([row], altered, now=datetime.now(UTC))
    packet["offers"].append(packet["offers"][0].copy())
    with pytest.raises(ValueError, match="duplicate"):
        prepare_batch([row], packet, now=datetime.now(UTC))


def test_batch_writes_only_bounded_exact_offer_values() -> None:
    row = canonical()
    packet = evidence(row)
    output = prepare_batch([row], packet, now=datetime.now(UTC))
    assert len(output) == 1
    item = output[0]
    assert item["offer_id"] == row["offer_id"]
    assert item["identity_sha256"] == runtime_offer_snapshots.identity_hash(row)
    assert item["evidence_sha256"] != "a" * 64
    assert item["price"] == 119
    assert item["shipping_cost"] == 0
    assert "affiliate_url" not in item
    assert "product_url" not in item
    assert "network" not in item


def test_batch_apply_requires_owner_approval_without_network(monkeypatch) -> None:
    from scripts.prepare_dufynd_runtime_offer_batch import apply_batch

    monkeypatch.delenv("DUFYND_OFFER_BATCH_OWNER_GO", raising=False)
    with pytest.raises(PermissionError, match="approval"):
        apply_batch([], batch_id="batch-demo-20261023", owner_approval="batch-demo-20261023")


def test_migration_closes_public_data_api_and_keeps_audit() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "enable row level security" in sql
    assert "revoke all on public.dufynd_runtime_offer_snapshots_v1" in sql
    assert "from public, anon, authenticated" in sql
    assert "grant select, insert, update on public.dufynd_runtime_offer_snapshots_v1" in sql
    assert "dufynd_runtime_offer_snapshot_audit_v1" in sql
    assert "observation timestamps must advance strictly" in sql
    assert "No DELETE grant" in sql
    assert "verified_at < clock_timestamp() - interval '72 hours'" in sql


def test_no_extra_public_api_or_unverified_schema_changes() -> None:
    source = Path("examples/retail/api/main.py").read_text(encoding="utf-8")
    assert "offers = await run_in_threadpool(offer_store.offers_for, product_id)" in source
    assert "offer = await run_in_threadpool(offer_store.eligible_offer, offer_id)" in source
    assert "if offer is None or not _live_dufynd_offer_product(offer.product_id):" in source
    assert "target = offer_clickout_target(offer)" in source


def test_verified_batch_rejects_unapproved_partner_and_wrong_ean() -> None:
    row = canonical()
    packet = evidence(row)
    stamp = datetime.now(UTC)
    for bad_ean in ("3614272648426", "0000000000000", "", None):
        altered = json.loads(json.dumps(packet))
        altered["offers"][0]["ean"] = bad_ean
        with pytest.raises(ValueError, match="ean"):
            prepare_batch([row], altered, now=stamp)

    for field, bad in (("brand", "Wrong"), ("volume_ml", 50), ("concentration", "Parfum")):
        altered = json.loads(json.dumps(packet))
        altered["offers"][0][field] = bad
        with pytest.raises(ValueError, match="brand_concentration_or_volume"):
            prepare_batch([row], altered, now=stamp)

    with pytest.raises(ValueError, match="partner_or_approved"):
        prepare_batch(
            [row],
            packet,
            now=stamp,
            partners_payload={
                "partners": [
                    {
                        "merchant_id": "notino",
                        "status": "active_product_deeplink_only",
                        "verified_product_scope": [],
                        "live_routing_allowed": True,
                    }
                ]
            },
        )


def test_hold_can_revoke_a_row_without_new_affiliate_or_ean_approval() -> None:
    row = canonical()
    packet = evidence(row)
    packet["offers"][0]["decision"] = "hold"
    packet["offers"][0].pop("ean")
    result = prepare_batch([row], packet, now=datetime.now(UTC), partners_payload={"partners": []})
    assert result[0]["decision"] == "hold"


def test_runtime_rollout_preserves_legacy_rabanne_certification(monkeypatch) -> None:
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")
    monkeypatch.delenv("DUFYND_RUNTIME_OFFER_MERCHANTS", raising=False)
    raw = json.loads(OFFER_FILE.read_text(encoding="utf-8"))["offers"]
    rabanne = next(item for item in raw if item["offer_id"] == purchase_freshness.TARGET_OFFER)
    certificate = {
        "source": "certified_purchase_verification",
        "offer_contract": {k: v for k, v in rabanne.items() if k != "last_updated_at"},
        "max_age_hours": 72,
        "decision": "safe_evidence_refresh",
        "verified_at": datetime.now(UTC).isoformat(),
    }
    read_calls = []

    def fake_read(rows):
        read_calls.append(rows)
        return None  # DB outage on opted-in merchants cannot affect Rabanne.

    monkeypatch.setattr(runtime_offer_snapshots, "load_runtime_snapshots", fake_read)
    monkeypatch.setattr(
        purchase_freshness,
        "evidence_for",
        lambda offer_id: certificate if offer_id == rabanne["offer_id"] else None,
    )
    result = MerchantOfferStore(OFFER_FILE).eligible_offer(rabanne["offer_id"])
    assert result is not None
    assert result.price == rabanne["price"]
    assert result.affiliate_url == rabanne["affiliate_url"]
    assert not read_calls  # No Notino request on unrelated Rabanne clickout.

    notino = canonical()
    assert MerchantOfferStore(OFFER_FILE).eligible_offer(notino["offer_id"]) is None
    assert read_calls and read_calls[-1][0]["offer_id"] == notino["offer_id"]


def test_runtime_invalid_scope_or_selected_db_outage_fails_closed(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_MERCHANTS", "notino,,perfumetrader")
    monkeypatch.setattr(
        runtime_offer_snapshots,
        "load_runtime_snapshots",
        lambda _: pytest.fail("invalid scope must not make network request"),
    )
    assert MerchantOfferStore(OFFER_FILE).offers_for(canonical()["product_id"]) == []

    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_MERCHANTS", "notino")
    notino = canonical() | {
        "last_updated_at": datetime.now(UTC).isoformat(),
    }
    other = next(
        item
        for item in json.loads(OFFER_FILE.read_text(encoding="utf-8"))["offers"]
        if item["merchant_id"] == "douglas-de"
    ) | {
        "product_id": notino["product_id"],
        "last_updated_at": datetime.now(UTC).isoformat(),
        "in_stock": True,
    }
    fixture = tmp_path / "merchant_offers.json"
    fixture.write_text(json.dumps({"offers": [notino, other]}), encoding="utf-8")
    monkeypatch.setattr(runtime_offer_snapshots, "load_runtime_snapshots", lambda _: None)
    ranked = MerchantOfferStore(fixture).offers_for(notino["product_id"])
    assert [offer.offer_id for offer in ranked] == [other["offer_id"]]
    assert all(offer.merchant_id != "notino" for offer in ranked)


def test_batch_approval_cannot_be_reused_after_price_or_proof_change(monkeypatch) -> None:
    from scripts.prepare_dufynd_runtime_offer_batch import apply_batch

    row = canonical()
    packet = evidence(row)
    prepared = prepare_batch([row], packet, now=datetime.now(UTC))
    batch_id = packet["batch_id"]
    exact_scope = f"{batch_id}:{batch_digest(prepared, batch_id=batch_id)}"
    monkeypatch.setenv("DUFYND_OFFER_BATCH_OWNER_GO", exact_scope)

    changed_price = [prepared[0] | {"price": prepared[0]["price"] + 1}]
    changed_proof = [prepared[0] | {"evidence_sha256": "f" * 64}]
    for altered in (changed_price, changed_proof):
        with pytest.raises(PermissionError, match="content_owner_approval"):
            apply_batch(altered, batch_id=batch_id, owner_approval=exact_scope)
    assert batch_digest(prepared, batch_id=batch_id) != batch_digest(
        changed_price, batch_id=batch_id
    )



def test_batch_readback_rejects_missing_mismatched_or_retimed_rows() -> None:
    from scripts.prepare_dufynd_runtime_offer_batch import verify_written_batch

    row = canonical()
    prepared = prepare_batch([row], evidence(row), now=datetime.now(UTC))
    unchanged = json.loads(json.dumps(prepared))
    verify_written_batch(prepared, unchanged)
    for corrupt in (
        [],
        [unchanged[0] | {"offer_id": "other"}],
        [unchanged[0] | {"price": 800.0}],
        [unchanged[0] | {"shipping_cost": 8.50}],
        [unchanged[0] | {"identity_sha256": "0" * 64}],
        [unchanged[0] | {"in_stock": False}],
        [unchanged[0] | {"decision": "hold"}],
        [unchanged[0] | {"verified_at": "2026-10-20T00:00:00Z"}],
    ):
        with pytest.raises(RuntimeError, match="offer_batch_readback"):
            verify_written_batch(prepared, corrupt)


def test_approved_upsert_requires_exact_uncached_readback(monkeypatch) -> None:
    from scripts.prepare_dufynd_runtime_offer_batch import apply_batch, batch_digest

    row = canonical()
    packet = evidence(row)
    prepared = prepare_batch([row], packet, now=datetime.now(UTC))
    batch_id = packet["batch_id"]
    approval = f"{batch_id}:{batch_digest(prepared, batch_id=batch_id)}"
    monkeypatch.setenv("DUFYND_OFFER_BATCH_OWNER_GO", approval)
    monkeypatch.setenv("SUPABASE_URL", runtime_offer_snapshots.PROJECT_URL)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "synthetic-test-only-server-key-000000")
    calls = []

    def accepted(request):
        calls.append(request.method)
        assert str(request.url).startswith(runtime_offer_snapshots.PROJECT_URL)
        assert request.headers["apikey"] == "synthetic-test-only-server-key-000000"
        if request.method == "POST":
            return httpx.Response(201)
        return httpx.Response(200, json=prepared)

    apply_batch(
        prepared,
        batch_id=batch_id,
        owner_approval=approval,
        transport=httpx.MockTransport(accepted),
    )
    assert calls == ["POST", "GET"]

    calls.clear()

    def unconfirmed(request):
        calls.append(request.method)
        if request.method == "POST":
            return httpx.Response(201)
        return httpx.Response(200, json=[prepared[0] | {"price": 250.0}])

    with pytest.raises(RuntimeError, match="readback_money"):
        apply_batch(
            prepared,
            batch_id=batch_id,
            owner_approval=approval,
            transport=httpx.MockTransport(unconfirmed),
        )
    assert calls == ["POST", "GET"]
