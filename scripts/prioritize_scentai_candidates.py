from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

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

BRAND_ALIASES: dict[str, tuple[str, ...]] = {
    "yves saint laurent": ("ysl",),
    "jean paul gaultier": ("jpg",),
    "parfums de marly": ("pdm",),
    "dolce gabbana": ("d g", "dg"),
    "giorgio armani": ("armani",),
    "afnan perfumes": ("afnan",),
}

GENERIC_NAME_TOKENS = {
    "eau",
    "de",
    "parfum",
    "toilette",
    "intense",
    "elixir",
    "for",
    "him",
    "her",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize(value: object) -> str:
    text = unicodedata.normalize(
        "NFKD",
        str(value or ""),
    )
    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )
    text = (
        text.lower()
        .replace("ß", "ss")
        .replace("&", " ")
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def token_set(value: object) -> set[str]:
    return {
        token
        for token in normalize(value).split()
        if token
    }


def candidate_aliases(candidate: dict) -> list[str]:
    brand = normalize(candidate.get("brand"))
    name = normalize(candidate.get("canonical_name"))

    aliases = {
        name,
        f"{brand} {name}".strip(),
    }

    for brand_alias in BRAND_ALIASES.get(
        brand,
        (),
    ):
        aliases.add(
            f"{normalize(brand_alias)} {name}".strip()
        )

    return sorted(
        alias
        for alias in aliases
        if alias
    )


def query_matches_candidate(
    query: str,
    candidate: dict,
) -> bool:
    normalized_query = normalize(query)
    if not normalized_query:
        return False

    query_tokens = token_set(normalized_query)
    name = normalize(candidate.get("canonical_name"))
    name_tokens = token_set(name)

    for alias in candidate_aliases(candidate):
        if normalized_query == alias:
            return True

        alias_tokens = token_set(alias)
        if (
            len(alias_tokens) >= 2
            and alias_tokens.issubset(query_tokens)
        ):
            return True

    meaningful_name_tokens = {
        token
        for token in name_tokens
        if token not in GENERIC_NAME_TOKENS
    }

    # One-word names such as "Y" are intentionally not matched by loose
    # token containment because they would create false positives.
    return (
        len(meaningful_name_tokens) >= 1
        and all(
            len(token) >= 3
            for token in meaningful_name_tokens
        )
        and meaningful_name_tokens.issubset(query_tokens)
    )


def demand_points(
    *,
    total_searches: int,
    unique_sessions: int,
    no_result_events: int,
) -> int:
    search_points = (
        4 if total_searches >= 20
        else 3 if total_searches >= 10
        else 2 if total_searches >= 5
        else 1 if total_searches >= 2
        else 0
    )
    session_points = (
        3 if unique_sessions >= 10
        else 2 if unique_sessions >= 5
        else 1 if unique_sessions >= 2
        else 0
    )
    no_result_points = (
        3 if no_result_events >= 7
        else 2 if no_result_events >= 3
        else 1 if no_result_events >= 1
        else 0
    )

    return min(
        10,
        search_points
        + session_points
        + no_result_points,
    )


def aggregate_candidate_demand(
    candidate: dict,
    search_rows: list[dict],
) -> dict[str, Any]:
    matched_rows = [
        row
        for row in search_rows
        if query_matches_candidate(
            str(row.get("search_term") or ""),
            candidate,
        )
    ]

    total_searches = sum(
        int(row.get("search_events") or 0)
        + int(row.get("no_result_events") or 0)
        for row in matched_rows
    )
    no_result_events = sum(
        int(row.get("no_result_events") or 0)
        for row in matched_rows
    )

    # Unique sessions from aggregate rows cannot be safely summed because
    # the same anonymous session may appear in multiple search terms.
    # Use the strongest term's session count as a conservative proxy.
    unique_sessions_proxy = max(
        (
            int(row.get("unique_sessions") or 0)
            for row in matched_rows
        ),
        default=0,
    )

    score = demand_points(
        total_searches=total_searches,
        unique_sessions=unique_sessions_proxy,
        no_result_events=no_result_events,
    )

    return {
        "demand_score_10": score,
        "total_searches": total_searches,
        "no_result_events": no_result_events,
        "unique_sessions_proxy": unique_sessions_proxy,
        "matched_search_terms": sorted(
            {
                str(row.get("search_term") or "")
                for row in matched_rows
                if row.get("search_term")
            }
        ),
    }


SCORE_COMPONENT_CAPS = {
    "retailer_demand": 35.0,
    "community_strength": 30.0,
    "cross_merchant_coverage": 15.0,
    "trend_momentum": 10.0,
    "portfolio_fit": 10.0,
}


def selection_score_components(
    candidate: dict,
) -> dict[str, float] | None:
    components = candidate.get(
        "selection_score_components"
    )
    if not isinstance(components, dict):
        return None

    if not set(SCORE_COMPONENT_CAPS).issubset(components):
        return None

    try:
        values = {
            key: float(components[key])
            for key in SCORE_COMPONENT_CAPS
        }
    except (TypeError, ValueError):
        return None

    for key, value in values.items():
        if value < 0 or value > SCORE_COMPONENT_CAPS[key]:
            return None

    return values


def selection_score(candidate: dict) -> float | None:
    components = selection_score_components(candidate)
    if components is not None:
        return sum(components.values())

    raw = candidate.get("selection_score")

    if isinstance(raw, bool):
        return None

    if isinstance(raw, (int, float)):
        numeric = float(raw)
        if 0 <= numeric <= 100:
            return numeric

    return None


def demand_adjusted_selection_score(
    candidate: dict,
    *,
    demand_score: int,
) -> float | None:
    components = selection_score_components(candidate)
    if components is None:
        return selection_score(candidate)

    # First-party demand is one input to the existing 10-point
    # trend_momentum component. It can strengthen that component but can
    # never create points outside the policy's original 0-100 weights.
    adjusted = dict(components)
    adjusted["trend_momentum"] = max(
        adjusted["trend_momentum"],
        float(demand_score),
    )
    return sum(adjusted.values())


def research_priority_value(
    *,
    base_selection_score: float | None,
    adjusted_selection_score: float | None,
    demand_score: int,
    manual_priority: int,
) -> tuple[float, str]:
    if adjusted_selection_score is not None:
        # The fractional demand value is only a deterministic tie-breaker
        # between equal 0-100 scores; it is not part of the selection score.
        return (
            adjusted_selection_score
            + demand_score / 100.0,
            (
                "demand_adjusted_selection_score_then_demand"
                if adjusted_selection_score != base_selection_score
                else "selection_score_then_demand"
            ),
        )

    # Current backlog has no stored numeric selection score. Keep demand
    # clearly separate rather than fabricating missing evidence.
    return (
        demand_score
        + max(0, 2 - manual_priority) / 100.0,
        "demand_first_no_numeric_selection_score",
    )


def build_candidate_priority(
    candidates_payload: dict,
    staging_payload: dict,
    search_rows: list[dict],
) -> dict[str, Any]:
    staged_ids = {
        str(row.get("candidate_id") or "").strip()
        for row in staging_payload.get("products", [])
        if row.get("candidate_id")
    }

    all_candidates = candidates_payload.get(
        "products",
        [],
    )
    research_candidates = [
        candidate
        for candidate in all_candidates
        if str(candidate.get("candidate_id") or "").strip()
        not in staged_ids
    ]

    rows: list[dict[str, Any]] = []

    for candidate in research_candidates:
        demand = aggregate_candidate_demand(
            candidate,
            search_rows,
        )
        base_score = selection_score(candidate)
        adjusted_score = demand_adjusted_selection_score(
            candidate,
            demand_score=demand["demand_score_10"],
        )

        try:
            manual_priority = int(
                candidate.get("priority") or 99
            )
        except (TypeError, ValueError):
            manual_priority = 99

        priority_value, method = research_priority_value(
            base_selection_score=base_score,
            adjusted_selection_score=adjusted_score,
            demand_score=demand["demand_score_10"],
            manual_priority=manual_priority,
        )

        rows.append(
            {
                "candidate_id": candidate.get(
                    "candidate_id"
                ),
                "brand": candidate.get("brand"),
                "canonical_name": candidate.get(
                    "canonical_name"
                ),
                "segment": candidate.get("segment"),
                "target_group": candidate.get(
                    "target_group"
                ),
                "verification_status": candidate.get(
                    "verification_status"
                ),
                "manual_priority": manual_priority,
                "selection_score_100": base_score,
                "demand_adjusted_selection_score_100": adjusted_score,
                **demand,
                "research_priority_value": round(
                    priority_value,
                    2,
                ),
                "priority_method": method,
            }
        )

    rows.sort(
        key=lambda row: (
            -row["research_priority_value"],
            -row["demand_score_10"],
            row["manual_priority"],
            str(row["brand"] or "").casefold(),
            str(row["canonical_name"] or "").casefold(),
        )
    )

    matched_terms = {
        term
        for row in rows
        for term in row["matched_search_terms"]
    }

    unmatched_terms = []
    for search_row in search_rows:
        term = str(
            search_row.get("search_term") or ""
        ).strip()
        if not term or term in matched_terms:
            continue

        total = (
            int(search_row.get("search_events") or 0)
            + int(
                search_row.get(
                    "no_result_events"
                )
                or 0
            )
        )
        no_results = int(
            search_row.get(
                "no_result_events"
            )
            or 0
        )
        sessions = int(
            search_row.get(
                "unique_sessions"
            )
            or 0
        )

        unmatched_terms.append(
            {
                "search_term": term,
                "total_searches": total,
                "no_result_events": no_results,
                "unique_sessions": sessions,
                "demand_score_10": demand_points(
                    total_searches=total,
                    unique_sessions=sessions,
                    no_result_events=no_results,
                ),
            }
        )

    unmatched_terms.sort(
        key=lambda row: (
            -row["demand_score_10"],
            -row["no_result_events"],
            -row["total_searches"],
            -row["unique_sessions"],
            row["search_term"],
        )
    )

    return {
        "candidate_count": len(all_candidates),
        "staged_excluded_count": len(
            [
                candidate
                for candidate in all_candidates
                if str(
                    candidate.get(
                        "candidate_id"
                    )
                    or ""
                ).strip()
                in staged_ids
            ]
        ),
        "research_candidate_count": len(rows),
        "candidates_with_demand": sum(
            1
            for row in rows
            if row["demand_score_10"] > 0
        ),
        "rows": rows,
        "unmatched_demand_terms": unmatched_terms,
    }


def fetch_search_rows(
    *,
    max_rows: int,
) -> list[dict]:
    supabase_url = os.getenv(
        "SUPABASE_URL",
        "",
    ).strip()
    service_key = (
        os.getenv(
            "SUPABASE_SECRET_KEY",
            "",
        ).strip()
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
            "Prioritize not-yet-staged SCENTAI research candidates "
            "using first-party catalog demand without bypassing "
            "selection or promotion QA."
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
        "--demand-json",
        type=Path,
        default=None,
        help=(
            "Optional offline JSON with a search_rows array. "
            "Without it, search demand is read from Supabase."
        ),
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=5000,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
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
            raw = load_json(args.demand_json)
            search_rows = raw.get("search_rows")
            if not isinstance(search_rows, list):
                raise ValueError(
                    "demand JSON requires a search_rows array"
                )
        else:
            search_rows = fetch_search_rows(
                max_rows=args.max_rows,
            )

        report = build_candidate_priority(
            load_json(args.candidates),
            load_json(args.staging),
            search_rows,
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
        "SCENTAI candidate priority | "
        f"candidates={report['candidate_count']} | "
        f"staged_excluded={report['staged_excluded_count']} | "
        f"research={report['research_candidate_count']} | "
        f"with_demand={report['candidates_with_demand']}"
    )

    print("Research queue:")
    for index, row in enumerate(
        report["rows"][: args.limit],
        start=1,
    ):
        selection = (
            "-"
            if row["selection_score_100"] is None
            else f"{row['selection_score_100']:.1f}"
        )
        terms = (
            ", ".join(row["matched_search_terms"])
            or "-"
        )
        print(
            f"  {index:>2}. "
            f"{row['brand']} {row['canonical_name']} | "
            f"demand={row['demand_score_10']}/10 | "
            f"selection={selection}/100 | "
            f"searches={row['total_searches']} | "
            f"no_results={row['no_result_events']} | "
            f"terms={terms}"
        )

    print("Unmatched demand terms:")
    if not report["unmatched_demand_terms"]:
        print("  Keine.")
    else:
        for index, row in enumerate(
            report["unmatched_demand_terms"][: args.limit],
            start=1,
        ):
            print(
                f"  {index:>2}. {row['search_term']} | "
                f"demand={row['demand_score_10']}/10 | "
                f"searches={row['total_searches']} | "
                f"no_results={row['no_result_events']} | "
                f"sessions={row['unique_sessions']}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
