"""Offline reconciliation of owner-authorized CSV exports; no network or database writes.

Exact column mappings are supplied beside unmodified originals. Output contains
aggregates only: no order, transaction, event, session IDs or CSV free text.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

from scripts.report_dufynd_profitable_growth import identifier, marked_qa, timestamp

STATUSES = {"pending", "approved", "declined", "reversed"}
REQUIRED = {
    "transaction_id",
    "advertiser_id",
    "transaction_date",
    "sale_amount",
    "sale_currency",
    "commission",
    "commission_currency",
    "status",
    "transaction_type",
}
OPTIONAL = {
    "publisher_id",
    "network",
    "clickref4",
    "sid",
    "product_id",
    "offer_id",
    "original_action_id",
    "original",
    "posting_date",
}
MAX_BYTES = 20_000_000
MAX_ROWS = 50_000


def require(ok, code):
    if not ok:
        raise ValueError(code)


def date(value, spec=None):
    spec = spec or {}
    if spec.get("date_format", "iso8601") == "iso8601":
        result = timestamp(value)
        require(result is not None, "timezone_aware_date_required")
        return result
    result = datetime.strptime(value, spec["date_format"])
    if result.tzinfo is None:
        zone = ZoneInfo(spec["timezone"])
        a, b = result.replace(tzinfo=zone, fold=0), result.replace(tzinfo=zone, fold=1)
        require(a.utcoffset() == b.utcoffset(), "ambiguous_local_date")
        require(
            a.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == result,
            "nonexistent_local_date",
        )
        result = a
    return result.astimezone(UTC)


def money(value, mark):
    require(
        isinstance(value, str)
        and bool(re.fullmatch(r"-?\d{1,12}(?:" + re.escape(mark) + r"\d{1,6})?", value)),
        "invalid_money",
    )
    return Decimal(value.replace(mark, "."))


def currency(value):
    require(bool(re.fullmatch(r"[A-Z]{3}", value)), "invalid_currency")
    return value


def identity(value):
    require(
        isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value)),
        "invalid_identity",
    )
    return value


def event_key(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value
    ):
        return None
    return UUID(value).hex


def read_bound(path, expected, kind):
    path = path.resolve()
    if kind != "synthetic":
        require(
            not any((p / ".git").exists() for p in path.parents),
            "original_inputs_must_be_outside_git",
        )
    require(path.is_file() and path.stat().st_size <= MAX_BYTES, "input_size_or_path")
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == expected, "source_hash_mismatch")
    return data


def parse_csv(data: bytes, spec: dict) -> list[dict]:
    network = spec["network"]
    require(network in {"awin", "cj"}, "unsupported_network")
    publisher = identity(spec["publisher_id"])
    advertisers = spec["advertiser_ids"]
    require(
        isinstance(advertisers, list)
        and advertisers
        and all(isinstance(x, str) and x.isdigit() for x in advertisers),
        "advertiser_scope_required",
    )
    require(publisher.isdigit(), "publisher_scope_required")
    columns = spec["columns"]
    required = REQUIRED | ({"original_action_id", "original"} if network == "cj" else set())
    if spec.get("date_basis") == "posting":
        required |= {"posting_date"}
    require(required <= columns.keys() <= REQUIRED | OPTIONAL, "invalid_column_mapping")
    require(
        all(isinstance(v, str) and v for v in columns.values())
        and len(set(columns.values())) == len(columns),
        "ambiguous_column_mapping",
    )
    require(
        "publisher_id" in columns or spec.get("publisher_scope_verified") is True,
        "publisher_column_or_verified_report_scope_required",
    )
    status_map = spec["status_map"]
    require(status_map and set(status_map.values()) <= STATUSES, "invalid_status_mapping")
    type_map = spec["type_map"]
    require(type_map and set(type_map.values()) <= {"sale", "other"}, "invalid_type_mapping")
    require(spec["delimiter"] in {",", ";", "\t"}, "invalid_delimiter")
    require(spec["decimal_mark"] in {".", ","}, "invalid_decimal_mark")
    start, end, as_of = (date(spec[k]) for k in ("window_start", "window_end", "as_of"))
    require(start < end <= as_of, "invalid_report_window")
    require(spec.get("date_basis") in {"transaction", "posting"}, "date_basis_required")
    require(spec.get("all_statuses") is True, "all_status_report_required")
    require(spec.get("complete") is True, "complete_export_required")
    require(
        spec.get("row_granularity")
        == ("commission_totals" if network == "cj" else "transaction_totals"),
        "unsupported_row_granularity",
    )
    reader = csv.DictReader(
        io.StringIO(data.decode("utf-8-sig")), delimiter=spec["delimiter"], strict=True
    )
    headers = reader.fieldnames or []
    require(
        headers and len(set(headers)) == len(headers) and set(columns.values()) <= set(headers),
        "missing_or_duplicate_csv_headers",
    )
    rows = []
    for number, raw in enumerate(reader, 2):
        require(number <= MAX_ROWS + 1, "row_limit")
        require(None not in raw and all(v is not None for v in raw.values()), "ragged_csv_row")
        r = {k: raw[v].strip() for k, v in columns.items()}
        require(r.get("network", network).lower() == network, "network_mismatch")
        require(r.get("publisher_id", publisher) == publisher, "publisher_mismatch")
        require(r["advertiser_id"] in advertisers, "advertiser_mismatch")
        require(r["status"] in status_map, "unknown_status")
        require(r["transaction_type"] in type_map, "unknown_transaction_type")
        at = date(r["transaction_date"], spec)
        require(at <= as_of, "transaction_after_report")
        if spec["date_basis"] == "transaction":
            require(start <= at < end, "transaction_outside_report_window")
        else:
            posted = date(r["posting_date"], spec)
            require(start <= posted < end and at <= posted, "posting_outside_report_window")
        amount, commission = (
            money(r[k], spec["decimal_mark"]) for k in ("sale_amount", "commission")
        )
        original = True
        if network == "cj":
            require(r["original"].lower() in {"true", "false", "1", "0"}, "invalid_original_flag")
            original = r["original"].lower() in {"true", "1"}
        require(
            (amount >= 0 and commission >= 0) if original else (amount <= 0 and commission <= 0),
            "unsupported_amount_signs",
        )
        rows.append(
            {
                "network": network,
                "publisher": publisher,
                "advertiser": r["advertiser_id"],
                "id": identity(r["transaction_id"]),
                "at": at,
                "as_of": as_of,
                "amount": amount,
                "commission": commission,
                "currency": currency(r["sale_currency"]),
                "commission_currency": currency(r["commission_currency"]),
                "status": status_map[r["status"]],
                "type": type_map[r["transaction_type"]],
                "ref": r.get("clickref4" if network == "awin" else "sid", ""),
                "product": r.get("product_id", ""),
                "offer": r.get("offer_id", ""),
                "action": identity(r["original_action_id"]) if network == "cj" else "",
                "original": original,
            }
        )
    return rows


def latest_records(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[(r["network"], r["publisher"], r["advertiser"], r["id"])].append(r)
    latest, poisoned = [], set()
    diagnostics = Counter()
    for versions in groups.values():
        newest = max(r["as_of"] for r in versions)
        candidates = [r for r in versions if r["as_of"] == newest]
        # A later report may change status/amount, never silently rewrite the
        # merchant identity, reference, currencies or original action.
        stable = (
            "at",
            "ref",
            "product",
            "offer",
            "currency",
            "commission_currency",
            "action",
            "original",
            "type",
        )
        conflict = any(any(r[k] != versions[0][k] for k in stable) for r in versions)
        conflict |= any(r != candidates[0] for r in candidates)
        if conflict:
            diagnostics["conflicting_transactions"] += 1
            poisoned.update(
                (r["publisher"], r["advertiser"], r["action"])
                for r in versions
                if r["network"] == "cj"
            )
            continue
        diagnostics["duplicate_rows"] += len(candidates) - 1
        diagnostics["superseded_rows"] += len(versions) - len(candidates)
        latest.append(candidates[0].copy())
    return latest, poisoned, diagnostics


def cj_actions(rows, poisoned, diagnostics):
    output = [r for r in rows if r["network"] == "awin"]
    groups = defaultdict(list)
    for r in rows:
        if r["network"] == "cj":
            groups[(r["publisher"], r["advertiser"], r["action"])].append(r)
    for key, entries in groups.items():
        originals = [r for r in entries if r["original"]]
        if key in poisoned or len(originals) != 1:
            diagnostics["cj_incomplete_or_conflicting_actions"] += 1
            continue
        base = originals[0].copy()
        compatible = ("currency", "commission_currency", "type", "status")
        if any(
            any(r[k] != base[k] for k in compatible)
            or any(r[k] and r[k] != base[k] for k in ("ref", "product", "offer"))
            for r in entries
        ):
            diagnostics["cj_incomplete_or_conflicting_actions"] += 1
            continue
        base["amount"] = sum((r["amount"] for r in entries), Decimal(0))
        base["commission"] = sum((r["commission"] for r in entries), Decimal(0))
        if base["amount"] < 0 or base["commission"] < 0:
            diagnostics["cj_incomplete_or_conflicting_actions"] += 1
            continue
        if len(entries) > 1 and base["amount"] == base["commission"] == 0:
            base["status"] = "reversed"
        diagnostics["cj_corrections_applied"] += len(entries) - 1
        output.append(base)
    return output


def classify(r, index, qa_sessions, routes):
    ref = event_key(r["ref"])
    if ref is None:
        return "unmatched", "missing_or_legacy_reference", None
    matches = index.get(ref, [])
    if not matches:
        return "unmatched", "event_not_in_verified_extract", None
    if any(e != matches[0] for e in matches):
        return "unmatched", "ambiguous_event_id", None
    e = matches[0]
    at = timestamp(e.get("occurred_at"))
    if e.get("event") != "merchant_clickout" or at is None or at > r["at"]:
        return "unmatched", "not_a_prior_clickout", None
    eligible = [
        route
        for route in routes
        if (
            route["network"],
            route["publisher_id"],
            route["advertiser_id"],
            route["offer_id"],
            route["product_id"],
            route["merchant_id"],
        )
        == (
            r["network"],
            r["publisher"],
            r["advertiser"],
            e.get("offer_id"),
            e.get("product_id"),
            e.get("source"),
        )
        and date(route["event_reference_valid_from"])
        <= at
        < date(route["event_reference_valid_until"])
    ]
    if len(eligible) != 1:
        return "unmatched", "route_or_event_reference_version_unverified", None
    if (r["product"] and r["product"] != e.get("product_id")) or (
        r["offer"] and r["offer"] != e.get("offer_id")
    ):
        return "unmatched", "network_reference_dimensions_conflict", None
    if marked_qa(e) or e.get("session_internal_qa") is True or e.get("session_key") in qa_sessions:
        return "internal_qa", "verified_event_id", e
    if e.get("traffic_class") == "visitor" and e.get("session_internal_qa") is False:
        return "visitor_classified", "verified_event_id_not_human_verification", e
    return "unknown_origin", "verified_event_id_unknown_traffic", e


def reconcile(rows, bundle, routes, *, kind, sources):
    require(bool(sources) or not rows, "rows_without_source_evidence")
    index = defaultdict(list)
    qa_sessions = set()
    for e in bundle["events"]:
        key = event_key(e.get("event_id"))
        if key:
            index[key].append(e)
        if marked_qa(e) or e.get("session_internal_qa") is True:
            qa_sessions.add(e.get("session_key"))
    latest, poisoned, diagnostics = latest_records(rows)
    transactions = cj_actions(latest, poisoned, diagnostics)
    buckets, reasons, attribution = {}, Counter(), Counter()
    statuses = Counter({s: 0 for s in sorted(STATUSES)})
    for r in transactions:
        traffic, reason, event = classify(r, index, qa_sessions, routes)
        reasons[reason] += 1
        attribution[traffic] += 1
        statuses[r["status"]] += 1
        cohort = (
            tuple(
                identifier(event.get(k)) or ""
                for k in (
                    "acquisition_source",
                    "campaign_id",
                    "content_id",
                    "product_id",
                    "offer_id",
                )
            )
            if event
            else ("", "", "", "", "")
        )
        key = (
            r["network"],
            r["publisher"],
            r["advertiser"],
            traffic,
            r["status"],
            r["type"],
            r["currency"],
            r["commission_currency"],
            *cohort,
        )
        b = buckets.setdefault(
            key, {"transactions": 0, "sale_amount": Decimal(0), "reported_commission": Decimal(0)}
        )
        b["transactions"] += 1
        b["sale_amount"] += r["amount"]
        b["reported_commission"] += r["commission"]
    output = []
    names = (
        "network",
        "publisher_id",
        "advertiser_id",
        "traffic_class",
        "status",
        "transaction_type",
        "sale_currency",
        "commission_currency",
        "platform",
        "campaign_id",
        "content_id",
        "click_product_id",
        "click_offer_id",
    )
    for key, b in sorted(buckets.items()):
        output.append(
            {
                **dict(zip(names, key, strict=True)),
                "transactions": b["transactions"],
                "sale_amount": str(b["sale_amount"]),
                "reported_commission": str(b["reported_commission"]),
                "approved_commission": str(b["reported_commission"])
                if key[4] == "approved"
                else None,
            }
        )
    held = (
        diagnostics["conflicting_transactions"]
        + diagnostics["cj_incomplete_or_conflicting_actions"]
    )
    return {
        "version": 1,
        "read_only": True,
        "evidence_kind": kind,
        "measurement_status": "SYNTHETIC_TEST_ONLY"
        if kind == "synthetic"
        else (
            "PARTIAL_RECONCILIATION_HOLD"
            if held
            else "OWNER_AUTHORIZED_EXPORT_OBSERVATION"
            if sources
            else "UNKNOWN"
        ),
        "reconciliation_complete": bool(sources) and not held,
        "quarantined_groups": held,
        "network_data_available": bool(sources),
        "sources": sources,
        "observed_transactions": len(transactions) if sources else None,
        "statuses": dict(statuses) if sources else None,
        "attribution": dict(attribution),
        "unmatched_reasons": dict(reasons),
        "diagnostics": dict(diagnostics),
        "buckets": output,
        "total_revenue": None,
        "paid_commission": None,
        "limits": [
            "Only supplied export windows and revisions; later corrections unknown",
            "Approved is not paid; no currency conversion or combined-currency total",
            "Visitor classification does not independently establish a human customer",
            "Click attribution does not prove the purchased basket product",
            "Missing, conflicted and unmatched evidence never becomes proven zero",
            "Original source authenticity is owner-attested, not independently authenticated",
        ],
    }


def _reconcile_manifest(path: Path):
    require(path.stat().st_size <= 1_000_000, "manifest_size")
    m = json.loads(path.read_text())
    require(
        m.get("version") == 1 and m.get("owner_authorized") is True, "owner_authorization_required"
    )
    kind = m.get("evidence_kind")
    require(kind in {"synthetic", "owner_authorized_original"}, "evidence_kind_required")
    reports = m.get("reports", [])
    require(isinstance(reports, list) and len(reports) <= 20, "report_limit")
    bundle = {"events": []}
    routes = m.get("routes", [])
    for route in routes:
        require(identifier(route.get("proof_reference")), "route_proof_required")
        require(
            date(route["event_reference_valid_from"]) < date(route["event_reference_valid_until"]),
            "route_window_invalid",
        )
    if m.get("events"):
        spec = m["events"]
        bundle = json.loads(read_bound(path.parent / spec["file"], spec["sha256"], kind))
        require(
            bundle.get("source") == "scentai_analytics_events"
            and spec.get("server_export_verified") is True,
            "verified_server_export_required",
        )
        require(
            isinstance(bundle.get("events"), list)
            and len(bundle["events"]) <= MAX_ROWS
            and all(isinstance(e, dict) for e in bundle["events"]),
            "event_extract_invalid",
        )
    rows, sources = [], []
    for spec in reports:
        data = read_bound(path.parent / spec["file"], spec["sha256"], kind)
        parsed = parse_csv(data, spec)
        rows.extend(parsed)
        require(len(rows) <= MAX_ROWS, "total_row_limit")
        sources.append(
            {
                k: spec[k]
                for k in (
                    "network",
                    "publisher_id",
                    "advertiser_ids",
                    "sha256",
                    "as_of",
                    "window_start",
                    "window_end",
                    "date_basis",
                )
            }
        )
    return reconcile(rows, bundle, routes, kind=kind, sources=sources)


def reconcile_manifest(path: Path):
    try:
        return _reconcile_manifest(path)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, csv.Error) as exc:
        # Preserve only our fixed validation codes, never CSV or path contents.
        code = (
            str(exc)
            if type(exc) is ValueError and re.fullmatch(r"[a-z_]+", str(exc))
            else "invalid_network_manifest_or_export"
        )
        raise ValueError(code) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = reconcile_manifest(args.manifest)
    except (OSError, ValueError, KeyError, TypeError, csv.Error):
        # Never echo raw rows, paths, refs or upstream exception text.
        parser.error(
            "Network reconciliation rejected invalid/unverified input; no revenue inferred"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
