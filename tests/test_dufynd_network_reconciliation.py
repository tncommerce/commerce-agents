"""All CSV rows and identifiers here are artificial; no real sales fixtures."""

import csv
import hashlib
import io
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from scripts.dufynd_network_reconciliation import parse_csv, reconcile, reconcile_manifest

EVENT = "11111111-1111-4111-8111-111111111111"
EVENT2 = "22222222-2222-4222-8222-222222222222"
BASE = {
    "transaction_id": "synthetic-1",
    "publisher_id": "900001",
    "advertiser_id": "900002",
    "transaction_date": "2026-10-11T12:00:00Z",
    "sale_amount": "100.00",
    "sale_currency": "EUR",
    "commission": "5.00",
    "commission_currency": "EUR",
    "status": "approved",
    "transaction_type": "sale",
    "clickref4": EVENT.replace("-", ""),
    "sid": EVENT.replace("-", ""),
    "original_action_id": "action-1",
    "original": "true",
    "product_id": "product-synthetic",
    "offer_id": "offer-synthetic",
}


def spec(network="awin", **changes):
    keys = list(BASE)
    return {
        "network": network,
        "publisher_id": "900001",
        "advertiser_ids": ["900002"],
        "as_of": "2026-10-12T08:00:00Z",
        "window_start": "2026-10-01T00:00:00Z",
        "window_end": "2026-10-12T08:00:00Z",
        "date_basis": "transaction",
        "all_statuses": True,
        "complete": True,
        "row_granularity": "commission_totals" if network == "cj" else "transaction_totals",
        "columns": {k: k for k in keys},
        "status_map": {s: s for s in ("pending", "approved", "declined", "reversed")},
        "type_map": {"sale": "sale", "bonus": "other"},
        "delimiter": ",",
        "decimal_mark": ".",
        **changes,
    }


def csv_bytes(rows, headings=None, delimiter=","):
    stream = io.StringIO()
    w = csv.DictWriter(stream, fieldnames=headings or list(BASE), delimiter=delimiter)
    w.writeheader()
    w.writerows(rows)
    return stream.getvalue().encode()


def event(**changes):
    return {
        "event_id": EVENT,
        "session_key": "anonymous-synthetic",
        "occurred_at": "2026-10-11T11:00:00Z",
        "event": "merchant_clickout",
        "source": "merchant-synthetic",
        "product_id": "product-synthetic",
        "offer_id": "offer-synthetic",
        "traffic_class": "visitor",
        "session_internal_qa": False,
        "acquisition_source": "instagram",
        "campaign_id": "campaign-synthetic",
        "content_id": "content-synthetic",
        **changes,
    }


def route(network="awin", **changes):
    return {
        "network": network,
        "publisher_id": "900001",
        "advertiser_id": "900002",
        "offer_id": "offer-synthetic",
        "product_id": "product-synthetic",
        "merchant_id": "merchant-synthetic",
        "event_reference_valid_from": "2026-10-10T12:00:00Z",
        "event_reference_valid_until": "2026-10-12T08:00:00Z",
        "proof_reference": "synthetic-proof",
        **changes,
    }


def run(rows=None, *, network="awin", events=None, routes=None, parsed=None):
    rows = [BASE] if rows is None else rows
    return reconcile(
        parsed if parsed is not None else parse_csv(csv_bytes(rows), spec(network)),
        {"events": [event()] if events is None else events},
        [route(network)] if routes is None else routes,
        kind="synthetic",
        sources=[{"network": network}],
    )


def test_exact_awin_event_join_separates_sale_commission_and_has_no_raw_ids():
    r = run()
    assert r["measurement_status"] == "SYNTHETIC_TEST_ONLY"
    assert r["observed_transactions"] == 1
    assert r["attribution"] == {"visitor_classified": 1}
    assert r["buckets"][0]["approved_commission"] == "5.00"
    assert r["buckets"][0]["sale_amount"] == "100.00"
    assert r["buckets"][0]["click_product_id"] == "product-synthetic"
    assert r["paid_commission"] is None and r["total_revenue"] is None
    assert EVENT not in str(r) and EVENT.replace("-", "") not in str(r)
    assert "anonymous-synthetic" not in str(r) and "synthetic-1" not in str(r)


@pytest.mark.parametrize("network", ["awin", "cj"])
def test_only_network_specific_reference_is_used(network):
    r = run([{**BASE, "clickref4" if network == "awin" else "sid": "old-session"}], network=network)
    assert r["attribution"] == {"unmatched": 1}


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"clickref4": "anonymous-synthetic"}, "missing_or_legacy_reference"),
        ({"clickref4": EVENT2}, "event_not_in_verified_extract"),
        ({"product_id": "other"}, "network_reference_dimensions_conflict"),
        ({"offer_id": "other"}, "network_reference_dimensions_conflict"),
    ],
)
def test_no_fuzzy_session_or_dimension_attribution(change, reason):
    assert run([{**BASE, **change}])["unmatched_reasons"] == {reason: 1}


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"source": "wrong-merchant"}, "route_or_event_reference_version_unverified"),
        ({"offer_id": None}, "route_or_event_reference_version_unverified"),
        ({"occurred_at": "2026-10-09T11:00:00Z"}, "route_or_event_reference_version_unverified"),
        ({"occurred_at": "2026-10-11T13:00:00Z"}, "not_a_prior_clickout"),
        ({"event": "page_view"}, "not_a_prior_clickout"),
    ],
)
def test_only_proven_prior_clickout_with_current_reference_contract(change, reason):
    assert run(events=[event(**change)])["unmatched_reasons"] == {reason: 1}


def test_conflicting_event_ids_are_not_arbitrarily_joined():
    r = run(events=[event(), event(source="other")])
    assert r["unmatched_reasons"] == {"ambiguous_event_id": 1}
    assert run(events=[event(), event()])["attribution"] == {"visitor_classified": 1}


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"traffic_class": "internal_qa"}, "internal_qa"),
        ({"session_internal_qa": True}, "internal_qa"),
        ({"campaign_id": "qa-demo"}, "internal_qa"),
        ({"traffic_class": "unclassified"}, "unknown_origin"),
        ({"session_internal_qa": None}, "unknown_origin"),
    ],
)
def test_traffic_provenance_never_promotes_unknown_or_qa(change, expected):
    assert run(events=[event(**change)])["attribution"] == {expected: 1}


def test_qa_marker_elsewhere_in_session_overrides_claimed_visitor():
    r = run(
        events=[event(), event(event_id=EVENT2, traffic_class="internal_qa", event="page_view")]
    )
    assert r["attribution"] == {"internal_qa": 1}


def test_all_statuses_and_currencies_remain_separate():
    rows = [
        {
            **BASE,
            "transaction_id": str(i),
            "status": state,
            "sale_currency": cur,
            "commission_currency": cur,
        }
        for i, (state, cur) in enumerate(
            [
                ("pending", "EUR"),
                ("approved", "EUR"),
                ("declined", "EUR"),
                ("reversed", "EUR"),
                ("approved", "USD"),
            ]
        )
    ]
    r = run(rows)
    assert r["statuses"] == {"pending": 1, "approved": 2, "declined": 1, "reversed": 1}
    assert len(r["buckets"]) == 5
    assert all(b["approved_commission"] is None for b in r["buckets"] if b["status"] != "approved")


def test_awin_newer_reversal_replaces_approved_and_reimport_is_idempotent():
    approved = parse_csv(csv_bytes([BASE, BASE]), spec())
    reversal = parse_csv(
        csv_bytes([{**BASE, "status": "reversed"}]), spec(as_of="2026-10-12T09:00:00Z")
    )
    r = run(parsed=reversal + approved + reversal)
    assert r["observed_transactions"] == 1 and r["statuses"]["reversed"] == 1
    assert r["statuses"]["approved"] == 0
    assert r["buckets"][0]["approved_commission"] is None
    assert r["diagnostics"]["superseded_rows"] == 2


def test_equal_timestamp_conflict_is_quarantined_not_a_zero_report():
    parsed = parse_csv(csv_bytes([BASE, {**BASE, "commission": "6.00"}]), spec())
    r = reconcile(parsed, {"events": []}, [], kind="owner_authorized_original", sources=[{}])
    assert r["measurement_status"] == "PARTIAL_RECONCILIATION_HOLD"
    assert not r["reconciliation_complete"] and r["quarantined_groups"] == 1
    assert r["buckets"] == [] and r["total_revenue"] is None


@pytest.mark.parametrize(
    "amount,commission,status", [("-100.00", "-5.00", "reversed"), ("-40.00", "-2.00", "approved")]
)
def test_cj_delta_corrections_are_deduplicated_and_netted(amount, commission, status):
    correction = {
        **BASE,
        "transaction_id": "correction-1",
        "original": "false",
        "sale_amount": amount,
        "commission": commission,
        "sid": "",
    }
    r = run([BASE, correction, correction], network="cj")
    assert r["observed_transactions"] == 1 and r["statuses"][status] == 1
    assert r["diagnostics"]["cj_corrections_applied"] == 1
    assert r["buckets"][0]["reported_commission"] == ("0.00" if status == "reversed" else "3.00")
    assert r["attribution"] == {"visitor_classified": 1}


def test_cj_orphan_correction_and_conflicting_correction_hold_whole_action():
    correction = {
        **BASE,
        "transaction_id": "correction-1",
        "original": "false",
        "sale_amount": "-100",
        "commission": "-5",
    }
    assert run([correction], network="cj")["quarantined_groups"] == 1
    r = run([BASE, correction, {**correction, "commission": "-4"}], network="cj")
    assert r["buckets"] == [] and r["quarantined_groups"] > 0


@pytest.mark.parametrize(
    "change,error",
    [
        ({"publisher_id": "000"}, "publisher_mismatch"),
        ({"advertiser_id": "000"}, "advertiser_mismatch"),
        ({"status": "paid-ish"}, "unknown_status"),
        ({"commission": "NaN"}, "invalid_money"),
        ({"sale_amount": "1,234.50"}, "invalid_money"),
        ({"commission": "=1+2"}, "invalid_money"),
        ({"sale_currency": "euro"}, "invalid_currency"),
        ({"transaction_date": "2026-10-11"}, "timezone_aware_date_required"),
        ({"transaction_id": "person@example.com"}, "invalid_identity"),
        ({"transaction_type": "unknown"}, "unknown_transaction_type"),
        ({"transaction_date": "2026-09-30T12:00:00Z"}, "transaction_outside_report_window"),
    ],
)
def test_invalid_fields_fail_closed_without_row_values(change, error):
    with pytest.raises(ValueError, match=error):
        parse_csv(csv_bytes([{**BASE, **change}]), spec())


def test_localized_csv_and_explicit_timezone_without_guessing():
    row = {
        **BASE,
        "commission": "5,25",
        "sale_amount": "100,50",
        "transaction_date": "11.10.2026 14:00",
    }
    parsed = parse_csv(
        csv_bytes([row], delimiter=";"),
        spec(
            delimiter=";", decimal_mark=",", date_format="%d.%m.%Y %H:%M", timezone="Europe/Berlin"
        ),
    )
    assert str(parsed[0]["commission"]) == "5.25"
    assert parsed[0]["at"].isoformat() == "2026-10-11T12:00:00+00:00"


def test_duplicate_headers_ragged_rows_and_missing_required_columns_fail():
    with pytest.raises(ValueError, match="headers"):
        parse_csv(b"transaction_id,transaction_id\na,b\n", spec())
    with pytest.raises(ValueError, match="ragged"):
        parse_csv(csv_bytes([BASE]) + b"bad,row\n", spec())
    bad = spec()
    del bad["columns"]["commission"]
    with pytest.raises(ValueError, match="column_mapping"):
        parse_csv(csv_bytes([BASE]), bad)


def write_fixture(tmp_path, rows=None, network="awin", kind="synthetic"):
    raw = csv_bytes([BASE] if rows is None else rows)
    (tmp_path / "original.csv").write_bytes(raw)
    events = json.dumps({"source": "scentai_analytics_events", "events": [event()]}).encode()
    (tmp_path / "events.json").write_bytes(events)
    m = {
        "version": 1,
        "owner_authorized": True,
        "evidence_kind": kind,
        "reports": [
            {**spec(network), "file": "original.csv", "sha256": hashlib.sha256(raw).hexdigest()}
        ],
        "events": {
            "file": "events.json",
            "sha256": hashlib.sha256(events).hexdigest(),
            "server_export_verified": True,
        },
        "routes": [route(network)],
    }
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(m))
    return p, m


def test_no_report_is_unknown_and_explicit_empty_report_only_covers_its_window(tmp_path):
    p, m = write_fixture(tmp_path, [], kind="owner_authorized_original")
    r = reconcile_manifest(p)
    assert r["observed_transactions"] == 0 and r["reconciliation_complete"]
    assert r["total_revenue"] is None and r["sources"][0]["window_start"]
    m["reports"] = []
    p.write_text(json.dumps(m))
    r = reconcile_manifest(p)
    assert r["measurement_status"] == "UNKNOWN"
    assert r["observed_transactions"] is None and r["statuses"] is None


@pytest.mark.parametrize(
    "change,error",
    [
        ({"owner_authorized": False}, "owner_authorization"),
        ({"events": {"file": "events.json", "sha256": "0" * 64}}, "hash_mismatch"),
    ],
)
def test_manifest_authorization_and_hash_binding(tmp_path, change, error):
    p, m = write_fixture(tmp_path)
    m.update(change)
    p.write_text(json.dumps(m))
    with pytest.raises(ValueError, match=error):
        reconcile_manifest(p)


def test_originals_inside_git_are_refused(tmp_path):
    (tmp_path / ".git").mkdir()
    p, _ = write_fixture(tmp_path, kind="owner_authorized_original")
    with pytest.raises(ValueError, match="outside_git"):
        reconcile_manifest(p)


def test_unmapped_personal_fields_never_appear_in_output(tmp_path):
    p, m = write_fixture(tmp_path)
    data = csv_bytes([{**BASE, "Email": "private@example.com"}], headings=[*BASE, "Email"])
    (tmp_path / "original.csv").write_bytes(data)
    m["reports"][0]["sha256"] = hashlib.sha256(data).hexdigest()
    p.write_text(json.dumps(m))
    assert "private@example.com" not in json.dumps(reconcile_manifest(p))


def test_cli_and_existing_growth_reporter_keep_raw_data_private_and_missing_kpis_unknown(tmp_path):
    p, _ = write_fixture(tmp_path)
    repo = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [sys.executable, "-m", "scripts.dufynd_network_reconciliation", "--manifest", str(p)],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["observed_transactions"] == 1
    events_path = tmp_path / "growth.json"
    events_path.write_text(json.dumps([event()]))
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.report_dufynd_profitable_growth",
            "--input",
            str(events_path),
            "--end",
            "2026-10-12T08:00:00Z",
            "--network-manifest",
            str(p),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    report = json.loads(r.stdout)
    assert report["network_reconciliation"]["measurement_status"] == "SYNTHETIC_TEST_ONLY"
    assert report["content"][0]["affiliate_revenue_eur"] is None
    assert report["content"][0]["affiliate_conversions"] is None
    assert EVENT not in r.stdout


def test_row_identity_scope_prevents_cross_network_and_publisher_dedup():
    a = parse_csv(csv_bytes([BASE]), spec())
    b = parse_csv(csv_bytes([BASE]), spec("cj"))
    c = deepcopy(a)
    c[0]["publisher"] = "900009"
    r = run(parsed=a + b + c, routes=[route(), route("cj")])
    assert r["observed_transactions"] == 3
    assert r["attribution"] == {"visitor_classified": 2, "unmatched": 1}


@pytest.mark.parametrize(
    "changes",
    [
        {"complete": False},
        {"all_statuses": False},
        {"row_granularity": "basket_items"},
        {"date_basis": "guessed"},
    ],
)
def test_partial_or_wrong_granularity_exports_are_rejected(changes):
    with pytest.raises(ValueError):
        parse_csv(csv_bytes([BASE]), spec(**changes))


def test_publisher_absent_requires_verified_report_scope():
    s = spec()
    del s["columns"]["publisher_id"]
    with pytest.raises(ValueError, match="publisher_column"):
        parse_csv(csv_bytes([BASE]), s)
    s["publisher_scope_verified"] = True
    assert parse_csv(csv_bytes([BASE]), s)[0]["publisher"] == "900001"


def test_native_cj_status_mapping_does_not_claim_paid():
    s = spec(
        "cj",
        status_map={
            "new": "pending",
            "extended": "pending",
            "locked": "approved",
            "closed": "approved",
        },
    )
    rows = parse_csv(csv_bytes([{**BASE, "status": "closed"}]), s)
    r = run(network="cj", parsed=rows)
    assert r["statuses"]["approved"] == 1 and r["paid_commission"] is None


def test_cli_redacts_invalid_csv_values(tmp_path):
    p, _ = write_fixture(tmp_path, [{**BASE, "commission": "secret@example.com"}])
    r = subprocess.run(
        [sys.executable, "-m", "scripts.dufynd_network_reconciliation", "--manifest", str(p)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0 and not r.stdout
    assert "secret@example.com" not in r.stderr and "Traceback" not in r.stderr


def test_read_only_run_neither_opens_network_nor_changes_inputs(tmp_path, monkeypatch):
    import socket

    p, _ = write_fixture(tmp_path)
    before = {f.name: f.read_bytes() for f in tmp_path.iterdir()}

    def forbidden(*args, **kwargs):
        raise AssertionError("No network connection authorized")

    monkeypatch.setattr(socket, "socket", forbidden)
    reconcile_manifest(p)
    assert {f.name: f.read_bytes() for f in tmp_path.iterdir()} == before


def test_conflicting_route_proofs_and_uuid_shaped_legacy_reference_stay_unmatched():
    # Even an old session reference that resembles a UUID cannot join before the rollout.
    r = run(events=[event(occurred_at="2026-10-09T00:00:00Z")])
    assert r["attribution"] == {"unmatched": 1}
    assert run(routes=[route(), route()])["attribution"] == {"unmatched": 1}


def test_posting_window_validated_separately_from_older_event_date():
    s = spec(date_basis="posting")
    s["columns"]["posting_date"] = "Posted"
    row = {**BASE, "transaction_date": "2026-09-30T12:00:00Z", "Posted": "2026-10-11T12:00:00Z"}
    parsed = parse_csv(csv_bytes([row], headings=[*BASE, "Posted"]), s)
    assert parsed[0]["at"].day == 30
    row["Posted"] = "2026-09-30T12:00:00Z"
    with pytest.raises(ValueError, match="posting_outside"):
        parse_csv(csv_bytes([row], headings=[*BASE, "Posted"]), s)
