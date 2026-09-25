from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from examples.retail.api.mock_retail import MockRetail

from shopping_agent import ProductDetails, ShoppingSessionContext

DEFAULT_STAGING = Path("examples/retail/data/scentai_catalog_staging.json")

TYPO_CASES = {
    "SC-YSL-LIBRE-EDP-90": "Libra",
    "SC-PRADA-PARADOXE-EDP-90": "Paradoxe",
    "SC-BURBERRY-GODDESS-EDP-100": "Godess",
    "SC-VIKTOR-ROLF-SPICEBOMB-EXTREME-EDP-90": "Spicebomb Exteme",
    "SC-YSL-BLACK-OPIUM-EDP-90": "Black Opiun",
    "SC-CHLOE-CHLOE-EDP-100": "Chloe",
    "SC-LATTAFA-ANGHAM-EDP-100": "Angam",
    "SC-AMOUAGE-GUIDANCE-46-EXTRAIT-100": "Gudance 46",
    "SC-DIOR-HYPNOTIC-POISON-EDT-100": "Hypnotic Posion",
    "SC-AMOUAGE-REFLECTION-MAN-EDP-100": "Refelction Man",
    "SC-YSL-LA-NUIT-DE-LHOMME-EDT-100": "La Nuit de L Homne",
    "SC-TOM-FORD-OMBRE-LEATHER-EDP-100": "Omre Leather",
}


def load_staging(path: Path = DEFAULT_STAGING) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def staged_product_details(row: dict) -> ProductDetails:
    profile = row["fragrance_profile"]
    recommendation = profile["recommendation_profile"]
    scores = recommendation["scores"]
    community = row["community"]
    classification = row.get("classification", {})

    attributes = {
        "canonical_name": str(row["name"]),
        "target_group": ", ".join(classification.get("target_groups", [])),
        "audience_lean": str(classification.get("audience_lean") or ""),
        "main_accords": ", ".join(profile.get("community_accords", [])),
        "freshness": str(scores["freshness"]),
        "sweetness": str(scores["sweetness"]),
        "woodiness": str(scores["woodiness"]),
        "spiciness": str(scores["spiciness"]),
        "longevity": (
            "" if community.get("longevity_10") is None else str(community["longevity_10"])
        ),
        "projection": (
            "" if community.get("projection_10") is None else str(community["projection_10"])
        ),
        "community_rating_10": str(community.get("rating_10") or ""),
        "rating_source": str(community.get("source") or ""),
        "volume_ml": str(row["volume_ml"]),
        "concentration": str(row["concentration"]),
    }

    return ProductDetails(
        product_id=row["product_id"],
        title=(f"{row['brand']} {row['name']} {row['concentration']} {row['volume_ml']} ml"),
        brand=row["brand"],
        price=100.0,
        category="fragrance",
        rating=(
            round(float(community["rating_10"]) / 2, 1)
            if community.get("rating_10") is not None
            else None
        ),
        review_count=int(community.get("rating_count") or 0),
        attributes=attributes,
        in_stock=True,
        short_description=(
            f"{row['brand']} {row['name']} " + ", ".join(profile.get("community_accords", [])[:3])
        ),
    )


def staging_backend(staging: dict) -> MockRetail:
    backend = MockRetail()
    products = {
        row["product_id"]: staged_product_details(row) for row in staging.get("products", [])
    }

    # QA intentionally isolates the not-yet-live staging catalog so
    # existing live products cannot hide a staging regression.
    backend.products = products
    backend.variants = {}
    return backend


def data_quality_issues(staging: dict) -> list[str]:
    issues = []
    products = staging.get("products", [])

    product_ids = [str(row.get("product_id") or "") for row in products]
    candidate_ids = [str(row.get("candidate_id") or "") for row in products]

    if len(product_ids) != len(set(product_ids)):
        issues.append("duplicate_product_id")

    if len(candidate_ids) != len(set(candidate_ids)):
        issues.append("duplicate_candidate_id")

    for row in products:
        product_id = str(row.get("product_id") or "<missing>")
        required = (
            "candidate_id",
            "product_id",
            "brand",
            "name",
            "concentration",
            "volume_ml",
            "classification",
            "fragrance_profile",
            "community",
        )
        for field in required:
            if row.get(field) in (None, "", [], {}):
                issues.append(f"{product_id}:missing_{field}")

        scores = (
            row.get("fragrance_profile", {}).get("recommendation_profile", {}).get("scores", {})
        )
        for axis in (
            "freshness",
            "sweetness",
            "woodiness",
            "spiciness",
        ):
            value = scores.get(axis)
            if not isinstance(value, (int, float)):
                issues.append(f"{product_id}:missing_{axis}_score")
            elif not 1 <= float(value) <= 10:
                issues.append(f"{product_id}:invalid_{axis}_score")

        community = row.get("community", {})
        if not community.get("provisional"):
            if community.get("longevity_10") is None:
                issues.append(f"{product_id}:missing_longevity")
            if community.get("projection_10") is None:
                issues.append(f"{product_id}:missing_projection")

    return issues


def audience_score_issues(
    backend: MockRetail,
    staging: dict,
) -> list[str]:
    issues = []

    for row in staging.get("products", []):
        product = backend.products[row["product_id"]]
        groups = set(
            row.get("classification", {}).get(
                "target_groups",
                [],
            )
        )

        if groups == {"women"}:
            correct = backend._score(
                product,
                ["damenduft"],
                "Ich suche einen Damenduft",
            )
            opposite = backend._score(
                product,
                ["herrenduft"],
                "Ich suche einen Herrenduft",
            )
            if correct <= opposite:
                issues.append(f"{row['product_id']}:women_audience_score")

        if groups == {"men"}:
            correct = backend._score(
                product,
                ["herrenduft"],
                "Ich suche einen Herrenduft",
            )
            opposite = backend._score(
                product,
                ["damenduft"],
                "Ich suche einen Damenduft",
            )
            if correct <= opposite:
                issues.append(f"{row['product_id']}:men_audience_score")

        if "unisex" in groups:
            unisex = backend._score(
                product,
                ["unisex"],
                "Ich suche einen Unisex Duft",
            )
            neutral = backend._score(
                product,
                ["duft"],
                "Ich suche einen Duft",
            )
            if unisex <= neutral:
                issues.append(f"{row['product_id']}:unisex_audience_score")

    return issues


def exact_name_query(row: dict) -> str:
    name = str(row.get("name") or "").strip()
    brand = str(row.get("brand") or "").strip()

    if len(name) <= 2 and brand:
        return f"{brand} {name}"

    return name


async def exact_name_search_issues(
    backend: MockRetail,
    staging: dict,
) -> list[str]:
    issues = []
    session = ShoppingSessionContext(
        session_id="staging-exact-name-qa",
        user_id="scentai-qa",
    )

    for row in staging.get("products", []):
        results = await backend.search_products(
            session,
            exact_name_query(row),
            limit=4,
        )
        if not results or results[0].product_id != row["product_id"]:
            found = results[0].product_id if results else "none"
            issues.append(f"{row['product_id']}:exact_name_found_{found}")

    return issues


async def typo_search_issues(
    backend: MockRetail,
) -> list[str]:
    issues = []
    session = ShoppingSessionContext(
        session_id="staging-typo-qa",
        user_id="scentai-qa",
    )

    for product_id, query in TYPO_CASES.items():
        if product_id not in backend.products:
            issues.append(f"{product_id}:missing_typo_fixture")
            continue

        results = await backend.search_products(
            session,
            query,
            limit=4,
        )
        if not results or results[0].product_id != product_id:
            found = results[0].product_id if results else "none"
            issues.append(f"{product_id}:typo_{query!r}_found_{found}")

    return issues


async def run_qa(
    staging_path: Path = DEFAULT_STAGING,
) -> dict:
    staging = load_staging(staging_path)
    backend = staging_backend(staging)

    data_issues = data_quality_issues(staging)
    audience_issues = audience_score_issues(
        backend,
        staging,
    )
    exact_issues = await exact_name_search_issues(
        backend,
        staging,
    )
    typo_issues = await typo_search_issues(backend)

    issues = data_issues + audience_issues + exact_issues + typo_issues

    products = staging.get("products", [])

    return {
        "product_count": len(products),
        "checks": {
            "data_quality": {
                "passed": not data_issues,
                "issue_count": len(data_issues),
            },
            "audience_scoring": {
                "passed": not audience_issues,
                "issue_count": len(audience_issues),
            },
            "exact_name_search": {
                "passed": not exact_issues,
                "tested": len(products),
                "issue_count": len(exact_issues),
            },
            "typo_search": {
                "passed": not typo_issues,
                "tested": len(TYPO_CASES),
                "issue_count": len(typo_issues),
            },
            "budget_and_offer_qa": {
                "passed": None,
                "status": ("deferred_until_current_affiliate_offers_are_available"),
            },
        },
        "passed": not issues,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run pre-live search and recommendation QA against "
            "the isolated SCENTAI staging catalog."
        )
    )
    parser.add_argument(
        "--staging",
        type=Path,
        default=DEFAULT_STAGING,
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    args = parser.parse_args()

    result = asyncio.run(run_qa(args.staging))

    if args.machine_readable:
        print(
            json.dumps(
                result,
                ensure_ascii=False,
            )
        )
    else:
        print(
            f"SCENTAI STAGING QA | "
            f"Products: {result['product_count']} | "
            f"Status: "
            f"{'PASS' if result['passed'] else 'FAIL'}"
        )
        for name, check in result["checks"].items():
            print(f"- {name}: {check.get('status') or ('PASS' if check.get('passed') else 'FAIL')}")

        if result["issues"]:
            print("Issues:")
            for issue in result["issues"]:
                print(f"- {issue}")

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
