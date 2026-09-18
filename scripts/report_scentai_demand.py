from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx

DEFAULT_CATALOG = Path("examples/retail/data/catalog.json")
SEARCH_VIEW = "scentai_catalog_search_demand"
ENGAGEMENT_VIEW = "scentai_product_engagement"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def product_labels(catalog: dict) -> dict[str, str]:
    labels: dict[str, str] = {}

    for product in catalog.get("products", []):
        product_id = str(product.get("product_id") or "").strip()
        if not product_id:
            continue

        brand = str(product.get("brand") or "").strip()
        attributes = product.get("attributes") or {}
        canonical_name = str(
            attributes.get("canonical_name") or product.get("title") or product_id
        ).strip()

        label = " ".join(part for part in (brand, canonical_name) if part).strip()

        labels[product_id] = label or product_id

    return labels


def _number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _integer(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def build_demand_report(
    search_rows: list[dict],
    engagement_rows: list[dict],
    catalog: dict,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    labels = product_labels(catalog)

    searches = []
    for row in search_rows:
        successful = _integer(row.get("search_events"))
        no_result = _integer(row.get("no_result_events"))
        total = successful + no_result

        if total <= 0:
            continue

        avg_results = _number(row.get("avg_result_count"))
        no_result_rate = no_result / total

        searches.append(
            {
                "search_term": row.get("search_term"),
                "search_events": successful,
                "no_result_events": no_result,
                "total_searches": total,
                "unique_sessions": _integer(row.get("unique_sessions")),
                "avg_result_count": round(avg_results, 2),
                "no_result_rate": round(no_result_rate, 4),
                "last_searched_at": row.get("last_searched_at"),
            }
        )

    top_searches = sorted(
        searches,
        key=lambda row: (
            -row["total_searches"],
            -row["unique_sessions"],
            str(row["search_term"] or ""),
        ),
    )[:limit]

    top_no_results = sorted(
        (row for row in searches if row["no_result_events"] > 0),
        key=lambda row: (
            -row["no_result_events"],
            -row["unique_sessions"],
            -row["total_searches"],
            str(row["search_term"] or ""),
        ),
    )[:limit]

    weak_coverage = sorted(
        (row for row in searches if row["no_result_events"] > 0 or row["avg_result_count"] <= 2),
        key=lambda row: (
            -row["no_result_rate"],
            -row["total_searches"],
            row["avg_result_count"],
            str(row["search_term"] or ""),
        ),
    )[:limit]

    engagement = []
    for row in engagement_rows:
        product_id = str(row.get("product_id") or "").strip()
        if not product_id:
            continue

        engagement.append(
            {
                "product_id": product_id,
                "product": labels.get(
                    product_id,
                    product_id,
                ),
                "product_opens": _integer(row.get("product_opens")),
                "merchant_clickouts": _integer(row.get("merchant_clickouts")),
                "opening_sessions": _integer(row.get("opening_sessions")),
                "clickout_sessions": _integer(row.get("clickout_sessions")),
                "last_event_at": row.get("last_event_at"),
            }
        )

    top_product_opens = sorted(
        engagement,
        key=lambda row: (
            -row["product_opens"],
            -row["opening_sessions"],
            row["product"],
        ),
    )[:limit]

    top_clickouts = sorted(
        engagement,
        key=lambda row: (
            -row["merchant_clickouts"],
            -row["clickout_sessions"],
            -row["product_opens"],
            row["product"],
        ),
    )[:limit]

    return {
        "summary": {
            "tracked_search_terms": len(searches),
            "total_searches": sum(row["total_searches"] for row in searches),
            "no_result_events": sum(row["no_result_events"] for row in searches),
            "engaged_products": len(engagement),
            "product_opens": sum(row["product_opens"] for row in engagement),
            "merchant_clickouts": sum(row["merchant_clickouts"] for row in engagement),
        },
        "top_searches": top_searches,
        "top_no_results": top_no_results,
        "weak_coverage": weak_coverage,
        "top_product_opens": top_product_opens,
        "top_clickouts": top_clickouts,
    }


def fetch_view_rows(
    *,
    supabase_url: str,
    service_key: str,
    view: str,
    max_rows: int,
) -> list[dict]:
    headers = {
        "apikey": service_key,
        **(
            {
                "Authorization": f"Bearer {service_key}",
            }
            if service_key.startswith("eyJ")
            else {}
        ),
    }

    response = httpx.get(
        f"{supabase_url.rstrip('/')}/rest/v1/{view}",
        params={
            "select": "*",
            "limit": str(max_rows),
        },
        headers=headers,
        timeout=15.0,
    )
    response.raise_for_status()

    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError(f"Unexpected Supabase response for {view}")

    return payload


def print_table(
    title: str,
    rows: list[dict],
    columns: list[tuple[str, str]],
) -> None:
    print(title)
    if not rows:
        print("  Noch keine Daten.")
        return

    for index, row in enumerate(rows, start=1):
        parts = []
        for key, label in columns:
            parts.append(f"{label}={row.get(key)}")
        print(f"  {index:>2}. " + " | ".join(parts))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=("Show internal SCENTAI demand signals from first-party Supabase analytics.")
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
    if args.max_rows < 1 or args.max_rows > 10000:
        parser.error("--max-rows must be between 1 and 10000")

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
        search_rows = fetch_view_rows(
            supabase_url=supabase_url,
            service_key=service_key,
            view=SEARCH_VIEW,
            max_rows=args.max_rows,
        )
        engagement_rows = fetch_view_rows(
            supabase_url=supabase_url,
            service_key=service_key,
            view=ENGAGEMENT_VIEW,
            max_rows=args.max_rows,
        )
    except (
        httpx.HTTPError,
        ValueError,
    ) as exc:
        parser.error(f"Supabase demand report failed: {exc}")

    report = build_demand_report(
        search_rows,
        engagement_rows,
        load_json(args.catalog),
        limit=args.limit,
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
        "SCENTAI demand report | "
        f"searches={summary['total_searches']} | "
        f"no_results={summary['no_result_events']} | "
        f"product_opens={summary['product_opens']} | "
        f"clickouts={summary['merchant_clickouts']}"
    )

    print_table(
        "Top searches:",
        report["top_searches"],
        [
            ("search_term", "query"),
            ("total_searches", "searches"),
            ("unique_sessions", "sessions"),
            ("avg_result_count", "avg_results"),
        ],
    )
    print_table(
        "Top no-result searches:",
        report["top_no_results"],
        [
            ("search_term", "query"),
            ("no_result_events", "no_results"),
            ("unique_sessions", "sessions"),
        ],
    )
    print_table(
        "Weak catalog coverage:",
        report["weak_coverage"],
        [
            ("search_term", "query"),
            ("no_result_rate", "no_result_rate"),
            ("total_searches", "searches"),
            ("avg_result_count", "avg_results"),
        ],
    )
    print_table(
        "Top product opens:",
        report["top_product_opens"],
        [
            ("product", "product"),
            ("product_opens", "opens"),
            ("opening_sessions", "sessions"),
        ],
    )
    print_table(
        "Top merchant clickouts:",
        report["top_clickouts"],
        [
            ("product", "product"),
            ("merchant_clickouts", "clickouts"),
            ("clickout_sessions", "sessions"),
        ],
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
