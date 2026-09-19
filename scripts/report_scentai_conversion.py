from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from scripts.report_scentai_demand import (
    fetch_view_rows,
    load_json,
    product_labels,
)

DEFAULT_CATALOG = Path("examples/retail/data/catalog.json")
FUNNEL_VIEW = "scentai_conversion_funnel"
PRODUCT_VIEW = "scentai_product_funnel"
POSITION_VIEW = "scentai_advisor_position_engagement"
SURFACE_VIEW = "scentai_clickout_surface_summary"
ACQUISITION_VIEW = "scentai_acquisition_funnel"
LIBRARY_VIEW = "scentai_personal_library_engagement"


def _integer(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(100.0 * numerator / denominator, 2)


def build_conversion_report(
    funnel_rows: list[dict],
    product_rows: list[dict],
    position_rows: list[dict],
    surface_rows: list[dict],
    catalog: dict,
    *,
    acquisition_rows: list[dict] | None = None,
    library_rows: list[dict] | None = None,
    limit: int = 20,
    minimum_sample_sessions: int = 10,
) -> dict[str, Any]:
    labels = product_labels(catalog)

    consultation_sessions = sum(_integer(row.get("consultation_sessions")) for row in funnel_rows)
    recommendation_sessions = sum(
        _integer(row.get("recommendation_sessions")) for row in funnel_rows
    )
    advisor_open_sessions = sum(_integer(row.get("advisor_open_sessions")) for row in funnel_rows)
    detail_view_sessions = sum(_integer(row.get("detail_view_sessions")) for row in funnel_rows)
    comparison_sessions = sum(_integer(row.get("comparison_sessions")) for row in funnel_rows)
    clickout_sessions = sum(_integer(row.get("clickout_sessions")) for row in funnel_rows)

    summary = {
        "consultation_sessions": consultation_sessions,
        "recommendation_sessions": recommendation_sessions,
        "advisor_open_sessions": advisor_open_sessions,
        "detail_view_sessions": detail_view_sessions,
        "comparison_sessions": comparison_sessions,
        "clickout_sessions": clickout_sessions,
        "consultation_to_recommendation_pct": _rate(
            recommendation_sessions,
            consultation_sessions,
        ),
        "recommendation_to_open_pct": _rate(
            advisor_open_sessions,
            recommendation_sessions,
        ),
        "recommendation_to_detail_pct": _rate(
            detail_view_sessions,
            recommendation_sessions,
        ),
        "recommendation_to_comparison_pct": _rate(
            comparison_sessions,
            recommendation_sessions,
        ),
        "recommendation_to_clickout_pct": _rate(
            clickout_sessions,
            recommendation_sessions,
        ),
    }

    products: list[dict[str, Any]] = []
    for row in product_rows:
        product_id = str(row.get("product_id") or "").strip()
        if not product_id:
            continue

        recommendation_count = _integer(row.get("recommendation_sessions"))

        products.append(
            {
                "product_id": product_id,
                "product": labels.get(product_id, product_id),
                "recommendation_views": _integer(row.get("recommendation_views")),
                "recommendation_sessions": recommendation_count,
                "advisor_open_sessions": _integer(row.get("advisor_open_sessions")),
                "detail_view_sessions": _integer(row.get("detail_view_sessions")),
                "comparison_sessions": _integer(row.get("comparison_sessions")),
                "clickout_sessions": _integer(row.get("clickout_sessions")),
                "advisor_open_rate_pct": (
                    None
                    if row.get("advisor_open_rate_pct") is None
                    else round(
                        _float(row.get("advisor_open_rate_pct")),
                        2,
                    )
                ),
                "recommendation_to_clickout_pct": (
                    None
                    if row.get("recommendation_to_clickout_pct") is None
                    else round(
                        _float(row.get("recommendation_to_clickout_pct")),
                        2,
                    )
                ),
                "sample_status": (
                    "sufficient_signal"
                    if recommendation_count >= minimum_sample_sessions
                    else "early_signal"
                ),
                "last_event_at": row.get("last_event_at"),
            }
        )

    top_clickout_products = sorted(
        products,
        key=lambda row: (
            -row["clickout_sessions"],
            -row["recommendation_sessions"],
            row["product"],
        ),
    )[:limit]

    top_open_products = sorted(
        products,
        key=lambda row: (
            -row["advisor_open_sessions"],
            -row["recommendation_sessions"],
            row["product"],
        ),
    )[:limit]

    mature_products = [row for row in products if row["sample_status"] == "sufficient_signal"]

    best_clickout_rates = sorted(
        mature_products,
        key=lambda row: (
            -(
                row["recommendation_to_clickout_pct"]
                if row["recommendation_to_clickout_pct"] is not None
                else -1.0
            ),
            -row["recommendation_sessions"],
            row["product"],
        ),
    )[:limit]

    positions: list[dict[str, Any]] = []
    for row in position_rows:
        position = _integer(row.get("item_position"))
        if position <= 0:
            continue

        sessions = _integer(row.get("recommendation_sessions"))

        positions.append(
            {
                "item_position": position,
                "recommendation_views": _integer(row.get("recommendation_views")),
                "recommendation_sessions": sessions,
                "advisor_open_sessions": _integer(row.get("advisor_open_sessions")),
                "open_rate_pct": (
                    None
                    if row.get("open_rate_pct") is None
                    else round(
                        _float(row.get("open_rate_pct")),
                        2,
                    )
                ),
                "sample_status": (
                    "sufficient_signal" if sessions >= minimum_sample_sessions else "early_signal"
                ),
            }
        )

    positions.sort(key=lambda row: row["item_position"])

    surfaces = [
        {
            "surface": str(row.get("surface") or "unknown"),
            "clickouts": _integer(row.get("clickouts")),
            "clickout_sessions": _integer(row.get("clickout_sessions")),
            "products_clicked": _integer(row.get("products_clicked")),
            "merchants_clicked": _integer(row.get("merchants_clicked")),
            "last_clickout_at": row.get("last_clickout_at"),
        }
        for row in surface_rows
    ]
    surfaces.sort(
        key=lambda row: (
            -row["clickout_sessions"],
            -row["clickouts"],
            row["surface"],
        )
    )

    cohorts = sorted(
        (
            {
                "cohort_date": row.get("cohort_date"),
                "consultation_sessions": _integer(row.get("consultation_sessions")),
                "recommendation_sessions": _integer(row.get("recommendation_sessions")),
                "advisor_open_sessions": _integer(row.get("advisor_open_sessions")),
                "detail_view_sessions": _integer(row.get("detail_view_sessions")),
                "comparison_sessions": _integer(row.get("comparison_sessions")),
                "clickout_sessions": _integer(row.get("clickout_sessions")),
                "recommendation_to_clickout_pct": (
                    None
                    if row.get("recommendation_to_clickout_pct") is None
                    else round(
                        _float(row.get("recommendation_to_clickout_pct")),
                        2,
                    )
                ),
            }
            for row in funnel_rows
        ),
        key=lambda row: str(row["cohort_date"] or ""),
        reverse=True,
    )

    acquisition_sources = []
    for row in acquisition_rows or []:
        landing_sessions = _integer(row.get("landing_sessions"))
        acquisition_sources.append(
            {
                "acquisition_source": str(row.get("acquisition_source") or "unknown"),
                "landing_sessions": landing_sessions,
                "consultation_sessions": _integer(row.get("consultation_sessions")),
                "recommendation_sessions": _integer(row.get("recommendation_sessions")),
                "detail_sessions": _integer(row.get("detail_sessions")),
                "comparison_sessions": _integer(row.get("comparison_sessions")),
                "clickout_sessions": _integer(row.get("clickout_sessions")),
                "landing_to_consultation_pct": (
                    None
                    if row.get("landing_to_consultation_pct") is None
                    else round(
                        _float(row.get("landing_to_consultation_pct")),
                        2,
                    )
                ),
                "consultation_to_recommendation_pct": (
                    None
                    if row.get("consultation_to_recommendation_pct") is None
                    else round(
                        _float(row.get("consultation_to_recommendation_pct")),
                        2,
                    )
                ),
                "landing_to_clickout_pct": (
                    None
                    if row.get("landing_to_clickout_pct") is None
                    else round(
                        _float(row.get("landing_to_clickout_pct")),
                        2,
                    )
                ),
                "sample_status": (
                    "sufficient_signal"
                    if landing_sessions >= minimum_sample_sessions
                    else "early_signal"
                ),
            }
        )

    acquisition_sources.sort(
        key=lambda row: (
            -row["landing_sessions"],
            row["acquisition_source"],
        )
    )

    library_engagement: list[dict[str, Any]] = []
    for row in library_rows or []:
        product_id = str(row.get("product_id") or "").strip()
        if not product_id:
            continue

        wishlist_sessions = _integer(
            row.get("wishlist_add_sessions")
        )
        collection_sessions = _integer(
            row.get("collection_add_sessions")
        )
        signal_sessions = max(
            wishlist_sessions,
            collection_sessions,
        )

        library_engagement.append(
            {
                "product_id": product_id,
                "product": labels.get(product_id, product_id),
                "wishlist_adds": _integer(
                    row.get("wishlist_adds")
                ),
                "wishlist_removes": _integer(
                    row.get("wishlist_removes")
                ),
                "collection_adds": _integer(
                    row.get("collection_adds")
                ),
                "collection_removes": _integer(
                    row.get("collection_removes")
                ),
                "wishlist_add_sessions": wishlist_sessions,
                "collection_add_sessions": collection_sessions,
                "sample_status": (
                    "sufficient_signal"
                    if signal_sessions
                    >= minimum_sample_sessions
                    else "early_signal"
                ),
                "last_event_at": row.get("last_event_at"),
            }
        )

    library_engagement.sort(
        key=lambda row: (
            -row["wishlist_add_sessions"],
            -row["collection_add_sessions"],
            row["product"],
        )
    )

    return {
        "minimum_sample_sessions": minimum_sample_sessions,
        "summary": summary,
        "recent_cohorts": cohorts[:limit],
        "top_clickout_products": top_clickout_products,
        "top_open_products": top_open_products,
        "best_clickout_rates": best_clickout_rates,
        "advisor_positions": positions,
        "clickout_surfaces": surfaces,
        "acquisition_sources": acquisition_sources,
        "personal_library_engagement": (
            library_engagement[:limit]
        ),
    }


def _print_rows(
    title: str,
    rows: list[dict],
    columns: list[tuple[str, str]],
) -> None:
    print(title)
    if not rows:
        print("  Noch keine Daten.")
        return

    for index, row in enumerate(rows, start=1):
        values = [f"{label}={row.get(key)}" for key, label in columns]
        print(f"  {index:>2}. " + " | ".join(values))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=("Report the privacy-minimized SCENTAI advisor-to-clickout conversion funnel.")
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
    )
    parser.add_argument(
        "--minimum-sample-sessions",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=5000,
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
    if args.minimum_sample_sessions < 1 or args.minimum_sample_sessions > 10000:
        parser.error("--minimum-sample-sessions must be between 1 and 10000")

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    service_key = (
        os.getenv("SUPABASE_SECRET_KEY", "").strip()
        or os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY",
            "",
        ).strip()
    )

    if not supabase_url or not service_key:
        parser.error(
            "SUPABASE_URL and SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY are required"
        )

    try:
        funnel_rows = fetch_view_rows(
            supabase_url=supabase_url,
            service_key=service_key,
            view=FUNNEL_VIEW,
            max_rows=args.max_rows,
        )
        product_rows = fetch_view_rows(
            supabase_url=supabase_url,
            service_key=service_key,
            view=PRODUCT_VIEW,
            max_rows=args.max_rows,
        )
        position_rows = fetch_view_rows(
            supabase_url=supabase_url,
            service_key=service_key,
            view=POSITION_VIEW,
            max_rows=args.max_rows,
        )
        surface_rows = fetch_view_rows(
            supabase_url=supabase_url,
            service_key=service_key,
            view=SURFACE_VIEW,
            max_rows=args.max_rows,
        )
        acquisition_rows = fetch_view_rows(
            supabase_url=supabase_url,
            service_key=service_key,
            view=ACQUISITION_VIEW,
            max_rows=args.max_rows,
        )
        library_rows = fetch_view_rows(
            supabase_url=supabase_url,
            service_key=service_key,
            view=LIBRARY_VIEW,
            max_rows=args.max_rows,
        )
    except Exception as exc:
        parser.error(f"Supabase conversion report failed: {exc}")

    report = build_conversion_report(
        funnel_rows,
        product_rows,
        position_rows,
        surface_rows,
        load_json(args.catalog),
        acquisition_rows=acquisition_rows,
        library_rows=library_rows,
        limit=args.limit,
        minimum_sample_sessions=args.minimum_sample_sessions,
    )

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

    summary = report["summary"]
    print(
        "SCENTAI conversion funnel | "
        f"consultations={summary['consultation_sessions']} | "
        f"recommendations={summary['recommendation_sessions']} | "
        f"opens={summary['advisor_open_sessions']} | "
        f"details={summary['detail_view_sessions']} | "
        f"comparisons={summary['comparison_sessions']} | "
        f"clickouts={summary['clickout_sessions']}"
    )
    print(
        "Rates | "
        f"consultation->recommendation="
        f"{summary['consultation_to_recommendation_pct']}% | "
        f"recommendation->open="
        f"{summary['recommendation_to_open_pct']}% | "
        f"recommendation->detail="
        f"{summary['recommendation_to_detail_pct']}% | "
        f"recommendation->comparison="
        f"{summary['recommendation_to_comparison_pct']}% | "
        f"recommendation->clickout="
        f"{summary['recommendation_to_clickout_pct']}%"
    )

    _print_rows(
        "Top products by clickout sessions:",
        report["top_clickout_products"],
        [
            ("product", "product"),
            ("recommendation_sessions", "recommended"),
            ("clickout_sessions", "clickouts"),
            (
                "recommendation_to_clickout_pct",
                "conversion_pct",
            ),
            ("sample_status", "sample"),
        ],
    )
    _print_rows(
        "Advisor positions:",
        report["advisor_positions"],
        [
            ("item_position", "position"),
            ("recommendation_sessions", "views"),
            ("advisor_open_sessions", "opens"),
            ("open_rate_pct", "open_rate_pct"),
            ("sample_status", "sample"),
        ],
    )
    _print_rows(
        "Clickout surfaces:",
        report["clickout_surfaces"],
        [
            ("surface", "surface"),
            ("clickout_sessions", "sessions"),
            ("clickouts", "clickouts"),
            ("products_clicked", "products"),
        ],
    )
    _print_rows(
        "Acquisition landing pages:",
        report["acquisition_sources"],
        [
            ("acquisition_source", "source"),
            ("landing_sessions", "landings"),
            ("consultation_sessions", "consultations"),
            ("clickout_sessions", "clickouts"),
            (
                "landing_to_consultation_pct",
                "consultation_pct",
            ),
            ("sample_status", "sample"),
        ],
    )
    _print_rows(
        "Personal library engagement:",
        report["personal_library_engagement"],
        [
            ("product", "product"),
            ("wishlist_add_sessions", "wishlist_sessions"),
            (
                "collection_add_sessions",
                "collection_sessions",
            ),
            ("sample_status", "sample"),
        ],
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
