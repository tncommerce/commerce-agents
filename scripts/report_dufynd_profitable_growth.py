"""Bounded, read-only organic funnel evidence; unknown sales never become zero."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

ORIGIN = "https://bqsdxaagklpkxioaqdqa.supabase.co"
COLUMNS = (
    "event_id,occurred_at,session_key,event,product_id,acquisition_source,campaign_id,content_id,"
    "traffic_class,source,surface"
)
PRODUCT_EVENTS = {"product_open", "fragrance_detail_view", "advisor_product_open"}
PLATFORMS = {"tiktok", "instagram", "youtube"}
IDENTIFIER = re.compile(r"[A-Za-z0-9._:-]{1,80}\Z")


def identifier(v: object) -> str | None:
    return v if isinstance(v, str) and IDENTIFIER.fullmatch(v) else None


def timestamp(v: object) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d.astimezone(UTC) if d.tzinfo is not None else None
    except ValueError:
        return None


def is_test(v: object) -> bool:
    return isinstance(v, str) and bool(
        re.search(r"(^|[._:\-])(qa|test|smoke|preview)([._:\-]|$)", v, re.I)
    )


def marked_qa(row: dict) -> bool:
    return row.get("traffic_class") == "internal_qa" or any(
        is_test(row.get(key))
        for key in (
            "session_key",
            "source",
            "surface",
            "acquisition_source",
            "campaign_id",
            "content_id",
        )
    )


def build_report(
    events: list[dict[str, Any]],
    *,
    start: datetime,
    end: datetime,
    complete: bool | None = None,
    minimum_sample: int = 30,
) -> dict[str, Any]:
    """Qualification is an observed tagged landing followed by product interest.

    Counts represent anonymous analytics sessions, never identifiable people.
    A content/campaign/platform cohort cannot borrow another cohort's landing.
    No attribution guessing, tracking writes, affiliate clicks or sales import.
    """
    if start.tzinfo is None or end.tzinfo is None or not start < end:
        raise ValueError("An explicit nonempty timezone-aware window is required")
    if minimum_sample < 1:
        raise ValueError("minimum_sample must be positive")
    seen = set()
    counts = Counter()
    groups: dict[tuple, list[dict]] = defaultdict(list)
    untagged = qa = unclassified = invalid = duplicate = 0
    # Defense for offline extracts; the live view also excludes QA markers
    # anywhere in a session, including rows outside this reporting window.
    qa_sessions = {r.get("session_key") for r in events if marked_qa(r)}
    landing_sessions = set()
    for row in events:
        at = timestamp(row.get("occurred_at"))
        event_id = identifier(row.get("event_id"))
        session = identifier(row.get("session_key"))
        if at is None or not event_id or not session:
            invalid += 1
            continue
        if not start <= at < end:
            continue
        if event_id in seen:
            duplicate += 1
            continue
        seen.add(event_id)
        content = identifier(row.get("content_id"))
        campaign = identifier(row.get("campaign_id"))
        platform = identifier(row.get("acquisition_source"))
        if marked_qa(row) or session in qa_sessions:
            qa += 1
            continue
        if row.get("traffic_class") != "visitor":
            unclassified += 1
            continue
        event = row.get("event")
        if event not in PRODUCT_EVENTS | {"page_view", "merchant_clickout"}:
            continue
        counts[event] += 1
        if event == "page_view":
            landing_sessions.add(session)
        if not content or not campaign or platform not in PLATFORMS:
            untagged += 1
            continue
        groups[(platform, campaign, content)].append(
            {
                "at": at,
                "session": session,
                "event": event,
                "product_id": identifier(row.get("product_id")),
            }
        )
    output = []
    all_qualified = set()
    for (platform, campaign, content), rows in sorted(groups.items()):
        sessions: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            sessions[row["session"]].append(row)
        landed, qualified, clickers = set(), set(), set()
        products = set()
        raw_clickouts = 0
        for session, journey in sessions.items():
            land_at = None
            interest_at = None
            for r in sorted(journey, key=lambda r: r["at"]):
                if r["event"] == "page_view":
                    landed.add(session)
                    if land_at is None:
                        land_at = r["at"]
                if r["event"] in PRODUCT_EVENTS and r["product_id"]:
                    products.add(r["product_id"])
                    if land_at is not None and r["at"] > land_at:
                        qualified.add(session)
                        if interest_at is None:
                            interest_at = r["at"]
                if r["event"] == "merchant_clickout":
                    raw_clickouts += 1
                    if interest_at is not None and r["at"] > interest_at:
                        clickers.add(session)
        all_qualified.update(qualified)
        enough = len(qualified) >= minimum_sample
        output.append(
            {
                "platform": platform,
                "campaign_id": campaign,
                "content_id": content,
                "product_ids": sorted(products),
                "landing_sessions": len(landed),
                "product_view_events": sum(r["event"] in PRODUCT_EVENTS for r in rows),
                "qualified_visits_observed": len(qualified),
                "merchant_clickout_events": raw_clickouts,
                "qualified_clickout_sessions": len(clickers),
                "qualified_clickout_rate": round(len(clickers) / len(qualified), 4)
                if qualified
                else None,
                "minimum_sample_met": enough,
                "sample_and_extract_gate_met": enough and complete is True,
                "evidence_strength": "DIRECTIONAL_FIRST_PARTY_ONLY",
                "views": None,
                "impressions": None,
                "reach": None,
                "retention": None,
                "completion": None,
                "saves": None,
                "shares": None,
                "social_to_dufynd_ctr": None,
                "affiliate_conversions": None,
                "affiliate_revenue_eur": None,
                "revenue_per_content_piece_eur": None,
                "revenue_per_1000_qualified_visits_eur": None,
                "owner_minutes": None,
                "content_cost_eur": None,
                "measurement_status": "FIRST_PARTY_ONLY_NO_VERIFIED_REVENUE",
            }
        )
    return {
        "version": 2,
        "read_only": True,
        "window": {"start": start.isoformat(), "end_exclusive": end.isoformat()},
        "coverage": {
            "event_extract_complete": complete,
            "ingestion_completeness": "UNKNOWN",
            "source_view": "dufynd_visitor_analytics",
            "traffic_provenance": "explicit_visitor_only_excludes_qa_sessions_and_unclassified",
            "offline_session_coverage": "limited_to_supplied_rows",
            "bot_owner_and_unmarked_qa_exclusion": "NOT_ESTABLISHED",
            "qualification": "tagged_social_landing_then_product_interest_same_session_and_cohort",
            "minimum_sample": minimum_sample,
            "sample_threshold_is_not_statistical_significance": True,
            "affiliate_conversion_revenue": "UNAVAILABLE",
        },
        "summary": {
            "observed_landing_sessions": len(landing_sessions),
            "qualified_visits_observed": len(all_qualified),
            "content_cohorts": len(output),
            "events_by_type": dict(counts),
            "unattributed_funnel_events": untagged,
            "test_events_excluded": qa,
            "unclassified_events_excluded": unclassified,
            "invalid_events_skipped": invalid,
            "duplicate_events_skipped": duplicate,
        },
        "content": output,
    }


def fetch_events(
    *, key: str, start: datetime, end: datetime, max_events: int
) -> tuple[list[dict], bool | None]:
    if not key or not 1 <= max_events <= 50_000:
        raise ValueError("Server read key and bounded max_events required")
    headers = {"apikey": key, "Prefer": "count=exact"}
    if key.startswith("eyJ"):
        headers["Authorization"] = "Bearer " + key
    rows: list[dict] = []
    total = None
    with httpx.Client(timeout=10, follow_redirects=False) as client:
        while len(rows) < max_events:
            limit = min(1000, max_events - len(rows))
            r = client.get(
                ORIGIN + "/rest/v1/dufynd_visitor_analytics",
                headers=headers,
                params={
                    "select": COLUMNS,
                    "occurred_at": "gte." + start.isoformat(),
                    "and": "(occurred_at.lt." + end.isoformat() + ")",
                    "order": "occurred_at.asc,event_id.asc",
                    "limit": str(limit),
                    "offset": str(len(rows)),
                },
            )
            if r.status_code not in {200, 206} or len(r.content) > 2_000_000:
                raise ValueError("Growth source unavailable")
            batch = r.json()
            if (
                not isinstance(batch, list)
                or len(batch) > limit
                or any(not isinstance(x, dict) for x in batch)
            ):
                raise ValueError("Invalid growth source projection")
            count = r.headers.get("content-range", "").rsplit("/", 1)[-1]
            current_total = int(count) if count.isdigit() else None
            if total is not None and total != current_total:
                raise ValueError("Source changed during extraction; retry")
            total = current_total
            rows.extend(batch)
            if not batch or (total is not None and len(rows) >= total):
                break
    return rows, len(rows) == total if total is not None else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, help="Offline projected event array; coverage remains unknown"
    )
    parser.add_argument("--days", type=int, choices=range(1, 31), default=7)
    parser.add_argument("--end", help="UTC/timezone-aware exclusive window end")
    parser.add_argument("--max-events", type=int, default=10_000)
    parser.add_argument("--minimum-sample", type=int, default=30)
    args = parser.parse_args()
    end = timestamp(args.end) if args.end else datetime.now(UTC)
    if end is None or args.minimum_sample < 1:
        parser.error("Valid timezone-aware end and positive minimum sample required")
    start = end - timedelta(days=args.days)
    try:
        if args.input:
            if args.input.stat().st_size > 20_000_000:
                raise ValueError("Offline input exceeds bound")
            rows = json.loads(args.input.read_text())
            if (
                not isinstance(rows, list)
                or len(rows) > 50_000
                or any(not isinstance(r, dict) for r in rows)
            ):
                raise ValueError("Invalid offline projection")
            complete = None
        else:
            rows, complete = fetch_events(
                key=os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
                start=start,
                end=end,
                max_events=args.max_events,
            )
        print(
            json.dumps(
                build_report(
                    rows,
                    start=start,
                    end=end,
                    complete=complete,
                    minimum_sample=args.minimum_sample,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    except (OSError, ValueError, httpx.HTTPError):
        parser.error("Growth evidence unavailable; no metrics fabricated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
