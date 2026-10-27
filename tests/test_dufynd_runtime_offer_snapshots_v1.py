"""No SKU leakage, stale prices, invented clicks or admin writes in dynamic mode."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, Lock, Thread

import httpx
import pytest
from scripts.prepare_dufynd_runtime_offer_batch import batch_digest, prepare_batch, triage_batch

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
    observed_at = (now or datetime.now(UTC)).isoformat()
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
                "verified_at": observed_at,
                "decision": "verified",
                "source_type": "official_network_feed",
                "source_ref": "network:cj-fixture-allowed",
                "evidence": {
                    "source_observation": "isolated-test-fixture-no-real-feed",
                    "source_evidence_kind": "exact_sku_stock_price_shipping_row",
                    "source_row_sha256": "a" * 64,
                    "source_observed_at": observed_at,
                },
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

    def read(selected, *, bypass_cache=False):
        calls.append(([offer["offer_id"] for offer in selected], bypass_cache))
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
    assert calls == [(expected_ids, False), ([row["offer_id"]], True)]


@pytest.mark.parametrize("database_result", [None, {}])
def test_no_database_observation_never_republishes_stale_file(monkeypatch, database_result) -> None:
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")
    monkeypatch.setattr(
        runtime_offer_snapshots,
        "load_runtime_snapshots",
        lambda _, **kwargs: database_result,
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
    packet["offers"][0]["hold_reason"] = "source_unavailable"
    packet["offers"][0].pop("ean")
    for field in ("price", "shipping_cost", "in_stock"):
        packet["offers"][0].pop(field)
    result = prepare_batch([row], packet, now=datetime.now(UTC), partners_payload={"partners": []})
    assert result[0]["decision"] == "hold"
    assert result[0]["price"] is None
    assert result[0]["shipping_cost"] is None
    assert result[0]["in_stock"] is None





@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("price", None),
        ("shipping_cost", None),
        ("in_stock", None),
        ("in_stock", False),
        ("in_stock", "true"),
    ],
)
def test_bulk_verified_offer_requires_complete_total_and_confirmed_stock(
    field, invalid,
) -> None:
    row = canonical()
    packet = evidence(row)
    packet["offers"][0][field] = invalid
    with pytest.raises(ValueError, match="verified_"):
        prepare_batch([row], packet, now=datetime.now(UTC))


def _source_hold(row: dict, reason: str = "source_unavailable") -> dict:
    packet = evidence(row)
    item = packet["offers"][0]
    item["decision"] = "hold"
    item["hold_reason"] = reason
    item.pop("ean")
    for field in ("price", "shipping_cost", "in_stock"):
        item.pop(field)
    return packet


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("price", 99.0),
        ("shipping_cost", 0),
        ("in_stock", False),
        ("in_stock", True),
    ],
)
def test_bulk_hold_cannot_carry_cached_positive_or_negative_commerce_claim(
    field, invalid,
) -> None:
    row = canonical()
    packet = _source_hold(row)
    packet["offers"][0][field] = invalid
    with pytest.raises(ValueError, match="hold_must_omit"):
        prepare_batch([row], packet, now=datetime.now(UTC), partners_payload={"partners": []})


def test_bulk_hold_requires_specific_reason_and_rebinds_proof_digest() -> None:
    row = canonical()
    first = _source_hold(row, "source_unavailable")
    second = _source_hold(row, "price_conflict")
    now = datetime.now(UTC)
    a = prepare_batch([row], first, now=now, partners_payload={"partners": []})
    b = prepare_batch([row], second, now=now, partners_payload={"partners": []})
    assert a[0]["decision"] == "hold" and b[0]["decision"] == "hold"
    assert a[0]["evidence_sha256"] != b[0]["evidence_sha256"]
    assert batch_digest(a, batch_id=first["batch_id"]) != batch_digest(
        b, batch_id=second["batch_id"]
    )
    first["offers"][0].pop("hold_reason")
    with pytest.raises(ValueError, match="explicit_hold_reason_required"):
        prepare_batch([row], first, now=now, partners_payload={"partners": []})


def test_verified_batch_cannot_hide_unchecked_delivery_with_unknown_shipping() -> None:
    row = canonical()
    packet = evidence(row)
    packet["offers"][0].pop("shipping_cost")
    with pytest.raises(ValueError, match="verified_total_shipping_missing"):
        prepare_batch([row], packet, now=datetime.now(UTC))




def test_fifty_offer_triage_envelope_and_exception_only_review() -> None:
    row = canonical()
    packet = evidence(row)
    # Positive exact source plus a well-formed but unapproved offer identifier.
    phantom = dict(packet["offers"][0])
    phantom["offer_id"] = "review-only-unreleased-offer"
    phantom["price"] = 1
    packet["offers"].append(phantom)
    report = triage_batch([row], packet, now=datetime.now(UTC))
    assert report["status"] == "REVIEW_ONLY_NO_IMPORT_OR_ACTIVATION"
    assert report["offer_count"] == 2
    assert report["counts"] == {
        "COMPLETE_EVIDENCE_REVIEW_ONLY": 1,
        "HOLD_REVIEW_ONLY": 0,
        "BLOCKED_SOURCE_EVIDENCE": 1,
    }
    assert report["items"][0]["offer_id"] == row["offer_id"]
    assert report["items"][1]["reason"] == "unknown_or_unreleased_offer"
    assert report["database_writes"] == 0
    assert report["affiliate_clickouts"] == 0
    assert report["public_offer_activation"] is False
    # No URLs, tracked links, old prices or proof material in the concise review.
    serialized = json.dumps(report)
    assert "affiliate_url" not in serialized
    assert "source_observation" not in serialized
    assert "119.0" not in serialized

    packet["offers"] = [dict(phantom, offer_id=f"review-unknown-{n}") for n in range(51)]
    with pytest.raises(ValueError, match="batch_size_out_of_bounds"):
        triage_batch([row], packet, now=datetime.now(UTC))
    packet["offers"] = [packet["offers"][0]] * 2
    with pytest.raises(ValueError, match="duplicate_offer_in_batch"):
        triage_batch([row], packet, now=datetime.now(UTC))


def test_triage_distinguishes_missing_shipping_from_source_hold_without_writes() -> None:
    row = canonical()
    packet = evidence(row)
    item = packet["offers"][0]
    item.pop("shipping_cost")
    invalid = triage_batch([row], packet, now=datetime.now(UTC))
    assert invalid["counts"]["BLOCKED_SOURCE_EVIDENCE"] == 1
    assert invalid["items"][0]["reason"] == "verified_total_shipping_missing"
    for field in ("price", "in_stock"):
        item.pop(field)
    item["decision"] = "hold"
    item["hold_reason"] = "shipping_unverified"
    held = triage_batch([row], packet, now=datetime.now(UTC),
                        partners_payload={"partners": []})
    assert held["counts"]["HOLD_REVIEW_ONLY"] == 1
    assert held["counts"]["BLOCKED_SOURCE_EVIDENCE"] == 0
    assert held["all_source_evidence_approved"] is False



def test_bulk_positive_offer_cannot_retimestamp_historical_observation() -> None:
    row = canonical()
    now = datetime.now(UTC)
    packet = evidence(row, now=now - timedelta(hours=48))
    packet["offers"][0]["verified_at"] = now.isoformat()
    with pytest.raises(ValueError, match="source_observation_not_equal_to_verified_at"):
        prepare_batch([row], packet, now=now)


@pytest.mark.parametrize("mutated_source", [
    {"source_observed_at": None},
    {"source_observed_at": "2026-08-01T00:00:00Z"},
    {"source_observed_at": "not-a-timestamp"},
    {"source_evidence_kind": "feed_import_timestamp_only"},
    {"source_row_sha256": ""},
    {"source_row_sha256": "g" * 64},
])
def test_bulk_positive_offer_requires_original_per_sku_source_time_and_digest(
    mutated_source: dict,
) -> None:
    row = canonical()
    packet = evidence(row)
    packet["offers"][0]["evidence"].update(mutated_source)
    with pytest.raises(ValueError, match="source_"):
        prepare_batch([row], packet, now=datetime.now(UTC))


def test_global_feed_import_time_never_refreshes_sku_price() -> None:
    row = canonical()
    packet = evidence(row)
    packet["offers"][0]["evidence"] = {
        "source_observation": "Awin import metadata 2026-10-26",
        "feed_imported_at": datetime.now(UTC).isoformat(),
        "source_evidence_kind": "feed_import_timestamp_only",
    }
    report = triage_batch([row], packet, now=datetime.now(UTC))
    assert report["counts"]["COMPLETE_EVIDENCE_REVIEW_ONLY"] == 0
    assert report["counts"]["BLOCKED_SOURCE_EVIDENCE"] == 1
    assert report["items"][0]["reason"] == "source_per_variant_evidence_kind_required"


def test_bulk_hold_does_not_need_false_positive_price_observation() -> None:
    row = canonical()
    packet = _source_hold(row)
    packet["offers"][0]["evidence"].pop("source_evidence_kind")
    packet["offers"][0]["evidence"].pop("source_row_sha256")
    packet["offers"][0]["evidence"].pop("source_observed_at")
    rows = prepare_batch([row], packet, now=datetime.now(UTC), partners_payload={"partners": []})
    assert rows[0]["decision"] == "hold"
    assert rows[0]["price"] is None
    assert rows[0]["shipping_cost"] is None



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

    def fake_read(rows, *, bypass_cache=False):
        read_calls.append((rows, bypass_cache))
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
    assert read_calls and read_calls[-1][0][0]["offer_id"] == notino["offer_id"]
    assert read_calls[-1][1] is True


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


def test_revoked_database_credentials_invalidate_cached_runtime_observation(
    monkeypatch,
) -> None:
    row = canonical()
    runtime_offer_snapshots._cache.clear()
    monkeypatch.setenv("SUPABASE_URL", runtime_offer_snapshots.PROJECT_URL)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_fixture_notino_version_a")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    requests = []
    original_client = httpx.Client

    def respond(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(runtime_offer_snapshots.PROJECT_URL)
        credential = request.headers["apikey"]
        requests.append(credential)
        amount = 119.0 if credential.endswith("version_a") else 125.0
        return httpx.Response(200, json=[snapshot(row) | {"price": amount}])

    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(
        runtime_offer_snapshots.httpx,
        "Client",
        lambda **kwargs: original_client(**kwargs, transport=transport),
    )

    first = runtime_offer_snapshots.load_runtime_snapshots([row])
    assert first[row["offer_id"]]["price"] == 119
    cached = runtime_offer_snapshots.load_runtime_snapshots([row])
    assert cached[row["offer_id"]]["price"] == 119
    assert len(requests) == 1

    # Removing the key must block even within an otherwise valid 30s cache.
    monkeypatch.delenv("SUPABASE_SECRET_KEY")
    assert runtime_offer_snapshots.load_runtime_snapshots([row]) is None
    assert len(requests) == 1

    # A different secret identity must perform a fresh source query.
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_fixture_notino_version_b")
    rotated = runtime_offer_snapshots.load_runtime_snapshots([row])
    assert rotated[row["offer_id"]]["price"] == 125
    assert len(requests) == 2

    monkeypatch.setenv("SUPABASE_URL", "https://wrong-project.invalid")
    assert runtime_offer_snapshots.load_runtime_snapshots([row]) is None
    assert len(requests) == 2
    runtime_offer_snapshots._cache.clear()


def test_runtime_partner_revocation_and_missing_registry_fail_closed(monkeypatch, tmp_path) -> None:
    row = canonical() | {"last_updated_at": datetime.now(UTC).isoformat()}
    offer_file = tmp_path / "merchant_offers.json"
    offer_file.write_text(json.dumps({"offers": [row]}), encoding="utf-8")
    partner_file = tmp_path / "merchant_partners.json"
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")
    monkeypatch.delenv("DUFYND_RUNTIME_OFFER_MERCHANTS", raising=False)
    reads = []

    def read(rows, *, bypass_cache=False):
        reads.extend(rows)
        assert bypass_cache is True
        return {row["offer_id"]: snapshot(row)}

    monkeypatch.setattr(runtime_offer_snapshots, "load_runtime_snapshots", read)
    store = MerchantOfferStore(offer_file)
    assert store.eligible_offer(row["offer_id"]) is None
    assert reads == []  # No query for an unapproved merchant.

    partner = {
        "merchant_id": "notino",
        "status": "active_product_deeplink_only",
        "live_routing_allowed": True,
        "verified_product_scope": [row["product_id"]],
    }
    partner_file.write_text(json.dumps({"partners": [partner]}), encoding="utf-8")
    allowed = store.eligible_offer(row["offer_id"])
    assert allowed is not None and allowed.price == 119
    assert len(reads) == 1

    partner["status"] = "paused"
    partner_file.write_text(json.dumps({"partners": [partner]}), encoding="utf-8")
    assert store.eligible_offer(row["offer_id"]) is None
    assert len(reads) == 1

    partner["status"] = "active_product_deeplink_only"
    partner["verified_product_scope"] = []
    partner_file.write_text(json.dumps({"partners": [partner]}), encoding="utf-8")
    assert store.eligible_offer(row["offer_id"]) is None
    assert len(reads) == 1


def test_runtime_offer_refuses_other_publishers_tracking_even_with_live_db(
    monkeypatch, tmp_path
) -> None:
    row = canonical()
    tampered = row | {
        "affiliate_url": row["affiliate_url"].replace("/click-101884613-", "/click-999999999-")
    }
    offer_file = tmp_path / "merchant_offers.json"
    offer_file.write_text(json.dumps({"offers": [tampered]}), encoding="utf-8")
    (tmp_path / "merchant_partners.json").write_text(
        json.dumps(
            {
                "partners": [
                    {
                        "merchant_id": "notino",
                        "status": "active_product_deeplink_only",
                        "live_routing_allowed": True,
                        "verified_product_scope": [row["product_id"]],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")

    def forbidden(_):
        pytest.fail("Foreign-publisher tracking must be rejected before DB read")

    monkeypatch.setattr(runtime_offer_snapshots, "load_runtime_snapshots", forbidden)
    assert MerchantOfferStore(offer_file).offers_for(row["product_id"]) == []


@pytest.mark.parametrize("revocation", ["hold", "out_of_stock", "network_error"])
def test_clickout_reads_fresh_snapshot_after_positive_listing_cache(
    monkeypatch,
    revocation,
) -> None:
    """An unexpired 30s listing cache cannot authorize a later buyer click."""
    row = canonical()
    runtime_offer_snapshots._cache.clear()
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_MERCHANTS", "notino")
    monkeypatch.setenv("SUPABASE_URL", runtime_offer_snapshots.PROJECT_URL)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_synthetic_clickout_test")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    calls = []
    original_httpx_client = httpx.Client

    def network(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "GET"
        assert str(request.url).startswith(runtime_offer_snapshots.PROJECT_URL)
        assert request.headers["apikey"] == "sb_secret_synthetic_clickout_test"
        if len(calls) == 1:
            return httpx.Response(200, json=[snapshot(row)])
        assert request.headers["Cache-Control"] == "no-store"
        if revocation == "network_error":
            return httpx.Response(503, json={"message": "not available"})
        changed = snapshot(row)
        if revocation == "hold":
            changed["decision"] = "hold"
        else:
            changed["in_stock"] = False
        return httpx.Response(200, json=[changed])

    transport = httpx.MockTransport(network)
    monkeypatch.setattr(
        runtime_offer_snapshots.httpx,
        "Client",
        lambda **kwargs: original_httpx_client(**kwargs, transport=transport),
    )
    store = MerchantOfferStore(OFFER_FILE)
    listing = store.offers_for(row["product_id"])
    assert listing and listing[0].offer_id == row["offer_id"]
    assert len(calls) == 1

    # A positive listing is displayed, but the clickout re-reads the DB.
    assert store.eligible_offer(row["offer_id"]) is None
    assert len(calls) == 2
    # A subsequent listing also sees the new hold/no-source state; no stale
    # positive cache is silently restored after the buyer-action decision.
    assert store.offers_for(row["product_id"]) == []
    assert len(calls) == 2
    runtime_offer_snapshots._cache.clear()


@pytest.mark.parametrize(
    ("age", "eligible"),
    [
        (timedelta(hours=1), True),
        (timedelta(hours=72), True),
        (timedelta(hours=72, seconds=1), False),
    ],
)
def test_runtime_disabled_clickout_never_triggers_new_database_bypass(
    monkeypatch,
    age,
    eligible,
) -> None:
    row = canonical()
    monkeypatch.delenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", raising=False)

    def forbidden(*args, **kwargs):
        pytest.fail("Legacy clickout cannot call runtime DB")

    monkeypatch.setattr(runtime_offer_snapshots, "load_runtime_snapshots", forbidden)
    store = MerchantOfferStore(OFFER_FILE)
    # A legitimate static refresh can be eligible. Its own source timestamp,
    # never the CI wall clock or a DB fallback, determines the 72-hour boundary.
    observed_at = datetime.fromisoformat(row["last_updated_at"].replace("Z", "+00:00"))
    offer = store.eligible_offer(row["offer_id"], now=observed_at + age)
    assert (offer is not None) is eligible
    if offer is not None:
        assert offer.last_updated_at == observed_at
        assert offer.price == row["price"]
        assert offer.affiliate_url == row["affiliate_url"]


def test_slower_old_listing_response_cannot_revive_newer_clickout_hold(monkeypatch) -> None:
    """Real overlapping queries: the slow positive GET must not override a new hold."""
    row = canonical()
    runtime_offer_snapshots._cache.clear()
    monkeypatch.setenv("SUPABASE_URL", runtime_offer_snapshots.PROJECT_URL)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_synthetic_cache_race_fixture")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    listing_started, allow_old_to_finish = Event(), Event()
    calls = []
    first_result = {}
    original_client = httpx.Client

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers.get("Cache-Control", "default"))
        if request.headers.get("Cache-Control") == "no-store":
            return httpx.Response(200, json=[snapshot(row) | {"decision": "hold"}])
        listing_started.set()
        if not allow_old_to_finish.wait(timeout=5):
            raise RuntimeError("test_barrier_timeout")
        return httpx.Response(200, json=[snapshot(row)])

    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(
        runtime_offer_snapshots.httpx,
        "Client",
        lambda **kwargs: original_client(**kwargs, transport=transport),
    )

    def slow_listing():
        first_result["value"] = runtime_offer_snapshots.load_runtime_snapshots([row])

    worker = Thread(target=slow_listing, daemon=True)
    worker.start()
    try:
        assert listing_started.wait(timeout=5)
        newer = runtime_offer_snapshots.load_runtime_snapshots([row], bypass_cache=True)
        assert newer[row["offer_id"]]["decision"] == "hold"
    finally:
        allow_old_to_finish.set()
        worker.join(timeout=5)

    assert not worker.is_alive()
    # Even the older in-flight caller receives the newer hold, not its own
    # stale positive HTTP response.
    assert first_result["value"][row["offer_id"]]["decision"] == "hold"
    # The stale query did complete after revocation, but cannot resurrect it.
    final = runtime_offer_snapshots.load_runtime_snapshots([row])
    assert final[row["offer_id"]]["decision"] == "hold"
    assert calls == ["default", "no-store"]
    runtime_offer_snapshots._cache.clear()


@pytest.mark.parametrize("corrupt", ["not_a_mapping", "duplicate_id", "foreign_id"])
def test_corrupt_supabase_response_cannot_partially_certify_offers(
    monkeypatch,
    corrupt,
) -> None:
    original = canonical()
    second = original | {"offer_id": "notino-fixture-second-offer"}
    runtime_offer_snapshots._cache.clear()
    monkeypatch.setenv("SUPABASE_URL", runtime_offer_snapshots.PROJECT_URL)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_synthetic_corrupt_response")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    if corrupt == "not_a_mapping":
        payload = [snapshot(original), "unexpected"]
    elif corrupt == "duplicate_id":
        payload = [snapshot(original), snapshot(original)]
    else:
        payload = [snapshot(original), snapshot(second) | {"offer_id": "foreign"}]
    original_client = httpx.Client
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    monkeypatch.setattr(
        runtime_offer_snapshots.httpx,
        "Client",
        lambda **kwargs: original_client(**kwargs, transport=transport),
    )
    assert runtime_offer_snapshots.load_runtime_snapshots([original, second]) is None
    runtime_offer_snapshots._cache.clear()


def test_slower_positive_buyer_clickout_cannot_override_faster_revocation(
    monkeypatch,
) -> None:
    """Two *uncached* buyer reads race; the first must not authorize stale stock."""
    row = canonical()
    runtime_offer_snapshots._cache.clear()
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")
    monkeypatch.setenv("SUPABASE_URL", runtime_offer_snapshots.PROJECT_URL)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_synthetic_double_clickout")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    entered = Event()
    release = Event()
    count_lock = Lock()
    request_count = [0]
    outcomes = []
    original_client = httpx.Client

    def network(request: httpx.Request) -> httpx.Response:
        assert request.headers["Cache-Control"] == "no-store"
        with count_lock:
            request_count[0] += 1
            index = request_count[0]
        if index == 1:
            entered.set()
            assert release.wait(timeout=5)
            return httpx.Response(200, json=[snapshot(row)])
        return httpx.Response(200, json=[snapshot(row) | {"decision": "hold"}])

    transport = httpx.MockTransport(network)
    monkeypatch.setattr(
        runtime_offer_snapshots.httpx,
        "Client",
        lambda **kwargs: original_client(**kwargs, transport=transport),
    )

    def first_buyer():
        outcomes.append(runtime_offer_snapshots.load_runtime_snapshots([row], bypass_cache=True))

    worker = Thread(target=first_buyer, daemon=True)
    worker.start()
    try:
        assert entered.wait(timeout=5)
        new_hold = runtime_offer_snapshots.load_runtime_snapshots([row], bypass_cache=True)
        assert new_hold[row["offer_id"]]["decision"] == "hold"
    finally:
        release.set()
        worker.join(timeout=5)

    assert not worker.is_alive()
    assert len(outcomes) == 1
    assert outcomes[0][row["offer_id"]]["decision"] == "hold"
    assert request_count[0] == 2
    runtime_offer_snapshots._cache.clear()


def test_cross_key_hold_revokes_cached_multi_offer_listing(monkeypatch) -> None:
    """One newer HOLD invalidates a still-cached two-offer product listing."""
    first = canonical()
    second = first | {"offer_id": "notino-multi-cache-second"}
    runtime_offer_snapshots._cache.clear()
    monkeypatch.setenv("SUPABASE_URL", runtime_offer_snapshots.PROJECT_URL)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_multi_offer_fixture")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    requests = []
    original_client = httpx.Client

    def source(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.headers.get("Cache-Control") == "no-store":
            return httpx.Response(200, json=[snapshot(first) | {"decision": "hold"}])
        decision = "verified" if len(requests) == 1 else "hold"
        return httpx.Response(
            200, json=[snapshot(first) | {"decision": decision}, snapshot(second)]
        )

    transport = httpx.MockTransport(source)
    monkeypatch.setattr(
        runtime_offer_snapshots.httpx,
        "Client",
        lambda **kwargs: original_client(**kwargs, transport=transport),
    )

    try:
        initial = runtime_offer_snapshots.load_runtime_snapshots([first, second])
        assert initial[first["offer_id"]]["decision"] == "verified"
        assert initial[second["offer_id"]]["decision"] == "verified"
        assert len(requests) == 1

        revoked = runtime_offer_snapshots.load_runtime_snapshots([first], bypass_cache=True)
        assert revoked[first["offer_id"]]["decision"] == "hold"
        assert len(requests) == 2

        updated = runtime_offer_snapshots.load_runtime_snapshots([first, second])
        assert len(requests) == 3
        assert updated[first["offer_id"]]["decision"] == "hold"
        assert updated[second["offer_id"]]["decision"] == "verified"
    finally:
        runtime_offer_snapshots._cache.clear()


@pytest.mark.parametrize("revocation", ["hold", "http_503"])
def test_slow_mixed_listing_cannot_resurrect_newer_one_offer_revocation(
    monkeypatch, revocation
) -> None:
    """A slow multi-ID result cannot override a newer single-ID revocation."""
    first = canonical()
    second = first | {"offer_id": "notino-slow-multi-second"}
    runtime_offer_snapshots._cache.clear()
    monkeypatch.setenv("SUPABASE_URL", runtime_offer_snapshots.PROJECT_URL)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_mixed_race_fixture")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    started, release = Event(), Event()
    values = []
    original_client = httpx.Client

    def source(request: httpx.Request) -> httpx.Response:
        if request.headers.get("Cache-Control") == "no-store":
            if revocation == "http_503":
                return httpx.Response(503, json={"message": "offline"})
            return httpx.Response(200, json=[snapshot(first) | {"decision": "hold"}])
        started.set()
        assert release.wait(timeout=5)
        return httpx.Response(200, json=[snapshot(first), snapshot(second)])

    transport = httpx.MockTransport(source)
    monkeypatch.setattr(
        runtime_offer_snapshots.httpx,
        "Client",
        lambda **kwargs: original_client(**kwargs, transport=transport),
    )

    worker = Thread(
        target=lambda: values.append(
            runtime_offer_snapshots.load_runtime_snapshots([first, second])
        ),
        daemon=True,
    )
    worker.start()
    try:
        assert started.wait(timeout=5)
        newer = runtime_offer_snapshots.load_runtime_snapshots([first], bypass_cache=True)
        if revocation == "hold":
            assert newer[first["offer_id"]]["decision"] == "hold"
        else:
            assert newer is None
    finally:
        release.set()
        worker.join(timeout=5)

    try:
        assert not worker.is_alive()
        assert len(values) == 1
        assert values[0][second["offer_id"]]["decision"] == "verified"
        if revocation == "hold":
            assert values[0][first["offer_id"]]["decision"] == "hold"
        else:
            assert first["offer_id"] not in values[0]
        cached = runtime_offer_snapshots.load_runtime_snapshots([first, second])
        assert cached == values[0]
    finally:
        runtime_offer_snapshots._cache.clear()


def test_batch_rejects_duplicate_or_invalid_released_canonical_ids() -> None:
    """A corrupt source registry must never silently choose the final SKU."""
    first = canonical()
    packet = evidence(first)
    now = datetime.now(UTC)
    with pytest.raises(ValueError, match="duplicate_canonical_offer_ids"):
        prepare_batch([first, first.copy()], packet, now=now)
    with pytest.raises(ValueError, match="invalid_canonical_offer_id"):
        prepare_batch([first | {"offer_id": None}], packet, now=now)
    with pytest.raises(ValueError, match="invalid_canonical_offer_rows"):
        prepare_batch([first, "corrupt"], packet, now=now)


@pytest.mark.parametrize(
    "bad_ref",
    ["   ", " proof ", "source\nrevoked", "source\tref", "x" * 261, ""],
)
def test_batch_rejects_empty_or_control_character_source_references(
    bad_ref: str,
) -> None:
    row = canonical()
    packet = evidence(row)
    packet["offers"][0]["source_ref"] = bad_ref
    with pytest.raises(ValueError, match="source_reference_required"):
        prepare_batch([row], packet, now=datetime.now(UTC))


@pytest.mark.parametrize("bad_observation", ["", "  \n\t", "x" * 2049, None])
def test_batch_rejects_missing_original_source_observation(
    bad_observation: str | None,
) -> None:
    row = canonical()
    packet = evidence(row)
    packet["offers"][0]["evidence"]["source_observation"] = bad_observation
    with pytest.raises(ValueError, match="source_observation_reference_required"):
        prepare_batch([row], packet, now=datetime.now(UTC))


@pytest.mark.parametrize(
    "bad_scope",
    [
        None,
        "SC-YSL-LIBRE-EDP-90",
        "SC-YSL-LIBRE-EDP-90-UNAPPROVED-SUFFIX",
        {"SC-YSL-LIBRE-EDP-90": True},
        ["SC-YSL-LIBRE-EDP-90", None],
    ],
)
def test_limited_partner_scope_must_be_exact_list(bad_scope) -> None:
    row = canonical()
    partners = {
        "partners": [
            {
                "merchant_id": "notino",
                "status": "active_product_deeplink_only",
                "live_routing_allowed": True,
                "verified_product_scope": bad_scope,
            }
        ]
    }
    assert runtime_offer_snapshots.approved_affiliate_route(row, partners) is False
    with pytest.raises(ValueError, match="partner_or_approved_tracked_route_missing"):
        prepare_batch([row], evidence(row), now=datetime.now(UTC), partners_payload=partners)


def test_limited_partner_scope_exact_released_list_still_passes() -> None:
    row = canonical()
    partners = {
        "partners": [
            {
                "merchant_id": "notino",
                "status": "active_product_deeplink_only",
                "live_routing_allowed": True,
                "verified_product_scope": [row["product_id"]],
            }
        ]
    }
    assert runtime_offer_snapshots.approved_affiliate_route(row, partners) is True
    prepared = prepare_batch([row], evidence(row), now=datetime.now(UTC), partners_payload=partners)
    assert prepared[0]["offer_id"] == row["offer_id"]


@pytest.mark.parametrize(
    ("offer_id", "shadow_parameter"),
    [
        ("notino-ysl-libre-edp-90", "URL=https%3A%2F%2Fother.invalid%2F"),
        ("perfumetrader-rabanne-1-million-edt-100", "AWINMID=31081"),
        ("perfumetrader-rabanne-1-million-edt-100", "AWINAFFID=1111"),
        (
            "perfumetrader-rabanne-1-million-edt-100",
            "UED=https%3A%2F%2Fother.invalid%2F",
        ),
        ("perfumetrader-rabanne-1-million-edt-100", "CLICKREF=other"),
    ],
)
def test_affiliate_route_rejects_case_variant_tracking_shadows(
    offer_id: str, shadow_parameter: str
) -> None:
    offers = json.loads(OFFER_FILE.read_text(encoding="utf-8"))["offers"]
    row = next(item for item in offers if item["offer_id"] == offer_id)
    partners = json.loads(
        OFFER_FILE.with_name("merchant_partners.json").read_text(encoding="utf-8")
    )
    assert runtime_offer_snapshots.approved_affiliate_route(row, partners) is True
    tampered = row | {"affiliate_url": row["affiliate_url"] + "&" + shadow_parameter}
    assert runtime_offer_snapshots.approved_affiliate_route(tampered, partners) is False


@pytest.mark.parametrize("control", ["\n", "\r", "\t"])
def test_affiliate_route_rejects_silently_stripped_url_controls(control: str) -> None:
    row = canonical()
    partners = json.loads(
        OFFER_FILE.with_name("merchant_partners.json").read_text(encoding="utf-8")
    )
    assert runtime_offer_snapshots.approved_affiliate_route(row, partners) is True
    tampered = row | {"affiliate_url": row["affiliate_url"] + "&sid=a" + control + "b"}
    assert runtime_offer_snapshots.approved_affiliate_route(tampered, partners) is False


@pytest.mark.parametrize(
    "malformed_payload",
    [
        "{invalid-json",
        "null",
        "{}",
        '{"offers": {"bad": "type"}}',
        '{"offers": [17]}',
        '{"offers": [{"offer_id": null}]}',
    ],
)
def test_malformed_released_offer_file_fails_closed_before_runtime_read(
    monkeypatch, tmp_path, malformed_payload: str
) -> None:
    offer_file = tmp_path / "merchant_offers.json"
    offer_file.write_text(malformed_payload, encoding="utf-8")
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid canonical file must never trigger a private DB call")

    monkeypatch.setattr(runtime_offer_snapshots, "load_runtime_snapshots", forbidden)
    store = MerchantOfferStore(offer_file)
    assert store.offers_for(canonical()["product_id"]) == []
    assert store.eligible_offer(canonical()["offer_id"]) is None


def test_duplicate_released_offer_ids_block_entire_buyer_surface(monkeypatch, tmp_path) -> None:
    row = canonical()
    offer_file = tmp_path / "merchant_offers.json"
    offer_file.write_text(json.dumps({"offers": [row, row | {"price": 1.0}]}), encoding="utf-8")

    def forbidden(*args, **kwargs):
        pytest.fail("Ambiguous offer IDs must never trigger a private DB call")

    monkeypatch.setattr(runtime_offer_snapshots, "load_runtime_snapshots", forbidden)
    store = MerchantOfferStore(offer_file)
    for enabled in (True, False):
        if enabled:
            monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")
        else:
            monkeypatch.delenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", raising=False)
        assert store.offers_for(row["product_id"]) == []
        assert store.eligible_offer(row["offer_id"]) is None


@pytest.mark.parametrize(
    "corruption",
    [
        {"price": "Infinity"},
        {"price": "not-a-number"},
        {"shipping_cost": "Infinity"},
        {"commission_rate": "Infinity"},
        {"last_updated_at": "not-a-timestamp"},
        {"merchant_name": None},
    ],
)
@pytest.mark.parametrize("runtime_enabled", [False, True])
def test_invalid_released_price_or_contract_fails_closed_before_buyer_read(
    monkeypatch, tmp_path, corruption: dict, runtime_enabled: bool
) -> None:
    row = canonical()
    offer_file = tmp_path / "merchant_offers.json"
    offer_file.write_text(json.dumps({"offers": [row | corruption]}), encoding="utf-8")
    if runtime_enabled:
        monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")
    else:
        monkeypatch.delenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", raising=False)

    def forbidden(*args, **kwargs):
        pytest.fail("Malformed canonical offer must not make any private API read")

    monkeypatch.setattr(runtime_offer_snapshots, "load_runtime_snapshots", forbidden)
    store = MerchantOfferStore(offer_file)
    assert store.offers_for(row["product_id"]) == []
    assert store.eligible_offer(row["offer_id"]) is None


def test_unrelated_corrupt_canonical_row_never_partially_serves_buyers(
    monkeypatch, tmp_path
) -> None:
    row = canonical()
    corrupted = row | {
        "offer_id": "unrelated-corrupt-eligible-claim",
        "product_id": "SC-UNRELATED-FAKE",
        "price": "Infinity",
    }
    offer_file = tmp_path / "merchant_offers.json"
    offer_file.write_text(json.dumps({"offers": [row, corrupted]}), encoding="utf-8")
    monkeypatch.setenv("DUFYND_RUNTIME_OFFER_SNAPSHOTS", "enabled")

    def forbidden(*args, **kwargs):
        pytest.fail("No private API call before validating the whole released file")

    monkeypatch.setattr(runtime_offer_snapshots, "load_runtime_snapshots", forbidden)
    store = MerchantOfferStore(offer_file)
    assert store.offers_for(row["product_id"]) == []
    assert store.eligible_offer(row["offer_id"]) is None
