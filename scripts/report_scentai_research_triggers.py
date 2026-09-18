from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from scripts.prioritize_scentai_candidates import (
    normalize,
    query_matches_candidate,
)
from scripts.report_scentai_demand import (
    SEARCH_VIEW,
    fetch_view_rows,
)


DEFAULT_CANDIDATES = Path(
    "examples/retail/data/scentai_catalog_candidates.json"
)
DEFAULT_STAGING = Path(
    "examples/retail/data/scentai_catalog_staging.json"
)
DEFAULT_CATALOG = Path(
    "examples/retail/data/catalog.json"
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def trigger_level(
    *,
    no_result_events: int,
    no_result_sessions: int,
) -> str | None:
    if no_result_events >= 7 and no_result_sessions >= 4:
        return "high"
    if no_result_events >= 3 and no_result_sessions >= 2:
        return "research"
    if no_result_events >= 1 and no_result_sessions >= 1:
        return "watch"
    return None


def live_identity_rows(catalog: dict) -> list[dict]:
    rows = []
    for product in catalog.get("products", []):
        product_id = str(product.get("product_id") or "")
        if not product_id.startswith("SC-"):
            continue

        attributes = product.get("attributes") or {}
        rows.append(
            {
                "product_id": product_id,
                "brand": product.get("brand"),
                "canonical_name": (
                    attributes.get("canonical_name")
                    or product.get("title")
                ),
            }
        )
    return rows


def staged_identity_rows(staging: dict) -> list[dict]:
    return [
        {
            "candidate_id": row.get("candidate_id"),
            "product_id": row.get("product_id"),
            "brand": row.get("brand"),
            "canonical_name": row.get("name"),
        }
        for row in staging.get("products", [])
    ]


def find_match(
    term: str,
    rows: list[dict],
) -> dict | None:
    for row in rows:
        if query_matches_candidate(term, row):
            return row
    return None


def classify_term(
    term: str,
    *,
    live_rows: list[dict],
    staged_rows: list[dict],
    candidate_rows: list[dict],
) -> dict[str, Any]:
    live = find_match(term, live_rows)
    if live is not None:
        return {
            "kind": "live_catalog",
            "matched_id": live.get("product_id"),
            "matched_name": " ".join(
                str(value or "").strip()
                for value in (
                    live.get("brand"),
                    live.get("canonical_name"),
                )
                if str(value or "").strip()
            ),
        }

    staged = find_match(term, staged_rows)
    if staged is not None:
        return {
            "kind": "verified_staging",
            "matched_id": (
                staged.get("candidate_id")
                or staged.get("product_id")
            ),
            "matched_name": " ".join(
                str(value or "").strip()
                for value in (
                    staged.get("brand"),
                    staged.get("canonical_name"),
                )
                if str(value or "").strip()
            ),
        }

    candidate = find_match(term, candidate_rows)
    if candidate is not None:
        return {
            "kind": "research_backlog",
            "matched_id": candidate.get("candidate_id"),
            "matched_name": " ".join(
                str(value or "").strip()
                for value in (
                    candidate.get("brand"),
                    candidate.get("canonical_name"),
                )
                if str(value or "").strip()
            ),
        }

    return {
        "kind": "new_research_opportunity",
        "matched_id": None,
        "matched_name": None,
    }


def recommended_action(
    *,
    kind: str,
    level: str,
) -> str:
    if kind == "live_catalog":
        return (
            "investigate_search_relevance_or_filtering"
            if level in {"research", "high"}
            else "monitor_search_relevance"
        )

    if kind == "verified_staging":
        return (
            "prioritize_existing_promotion_blockers"
            if level in {"research", "high"}
            else "monitor_until_affiliate_and_image_gates_clear"
        )

    if kind == "research_backlog":
        return (
            "prioritize_identity_and_evidence_research"
            if level in {"research", "high"}
            else "keep_in_research_watchlist"
        )

    return (
        "create_research_lead_for_manual_review"
        if level in {"research", "high"}
        else "monitor_before_adding_to_backlog"
    )


def build_trigger_report(
    search_rows: list[dict],
    candidates: dict,
    staging: dict,
    catalog: dict,
) -> dict[str, Any]:
    live_rows = live_identity_rows(catalog)
    staged_rows = staged_identity_rows(staging)
    candidate_rows = candidates.get("products", [])

    triggers = []

    for row in search_rows:
        term = str(row.get("search_term") or "").strip()
        if not term:
            continue

        no_results = int(row.get("no_result_events") or 0)
        no_result_sessions = int(
            row.get("no_result_sessions") or 0
        )

        level = trigger_level(
            no_result_events=no_results,
            no_result_sessions=no_result_sessions,
        )
        if level is None:
            continue

        classification = classify_term(
            term,
            live_rows=live_rows,
            staged_rows=staged_rows,
            candidate_rows=candidate_rows,
        )

        triggers.append(
            {
                "search_term": normalize(term),
                "level": level,
                "no_result_events": no_results,
                "no_result_sessions": no_result_sessions,
                "total_searches": (
                    int(row.get("search_events") or 0)
                    + no_results
                ),
                "unique_sessions": int(
                    row.get("unique_sessions") or 0
                ),
                "last_searched_at": row.get(
                    "last_searched_at"
                ),
                **classification,
                "recommended_action": recommended_action(
                    kind=classification["kind"],
                    level=level,
                ),
            }
        )

    level_rank = {
        "high": 0,
        "research": 1,
        "watch": 2,
    }
    kind_rank = {
        "new_research_opportunity": 0,
        "research_backlog": 1,
        "verified_staging": 2,
        "live_catalog": 3,
    }

    triggers.sort(
        key=lambda row: (
            level_rank[row["level"]],
            kind_rank[row["kind"]],
            -row["no_result_sessions"],
            -row["no_result_events"],
            -row["total_searches"],
            row["search_term"],
        )
    )

    counts_by_level = {
        level: sum(
            1 for row in triggers
            if row["level"] == level
        )
        for level in ("high", "research", "watch")
    }
    counts_by_kind = {
        kind: sum(
            1 for row in triggers
            if row["kind"] == kind
        )
        for kind in (
            "new_research_opportunity",
            "research_backlog",
            "verified_staging",
            "live_catalog",
        )
    }

    actionable = [
        row
        for row in triggers
        if row["level"] in {"research", "high"}
    ]

    return {
        "trigger_count": len(triggers),
        "actionable_count": len(actionable),
        "counts_by_level": counts_by_level,
        "counts_by_kind": counts_by_kind,
        "triggers": triggers,
    }


def fetch_search_rows(*, max_rows: int) -> list[dict]:
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    service_key = (
        os.getenv("SUPABASE_SECRET_KEY", "").strip()
        or os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY",
            "",
        ).strip()
    )

    if not supabase_url or not service_key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SECRET_KEY or "
            "SUPABASE_SERVICE_ROLE_KEY are required"
        )

    return fetch_view_rows(
        supabase_url=supabase_url,
        service_key=service_key,
        view=SEARCH_VIEW,
        max_rows=max_rows,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Surface SCENTAI research triggers from repeated "
            "zero-result catalog searches."
        )
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=DEFAULT_CANDIDATES,
    )
    parser.add_argument(
        "--staging",
        type=Path,
        default=DEFAULT_STAGING,
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
    )
    parser.add_argument(
        "--demand-json",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=5000,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    args = parser.parse_args()

    if args.limit < 1 or args.limit > 100:
        parser.error("--limit must be between 1 and 100")

    try:
        if args.demand_json is not None:
            payload = load_json(args.demand_json)
            search_rows = payload.get("search_rows")
            if not isinstance(search_rows, list):
                raise ValueError(
                    "demand JSON requires a search_rows array"
                )
        else:
            search_rows = fetch_search_rows(
                max_rows=args.max_rows
            )

        report = build_trigger_report(
            search_rows,
            load_json(args.candidates),
            load_json(args.staging),
            load_json(args.catalog),
        )
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        parser.error(str(exc))

    if args.output is not None:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        args.output.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
        return 0

    print(
        "SCENTAI research triggers | "
        f"total={report['trigger_count']} | "
        f"actionable={report['actionable_count']} | "
        f"high={report['counts_by_level']['high']} | "
        f"research={report['counts_by_level']['research']} | "
        f"watch={report['counts_by_level']['watch']}"
    )

    if not report["triggers"]:
        print("Keine Research-Trigger.")
        return 0

    for index, row in enumerate(
        report["triggers"][: args.limit],
        start=1,
    ):
        print(
            f"  {index:>2}. {row['level'].upper()} | "
            f"{row['search_term']} | "
            f"kind={row['kind']} | "
            f"no_results={row['no_result_events']} | "
            f"sessions={row['no_result_sessions']} | "
            f"action={row['recommended_action']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
