import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


DATABASE = Path("examples/retail/data/scentai_products.json")

ALLOWED_ROLES = {
    "benchmark",
    "clone",
    "inspired",
    "alternative",
}

ALLOWED_CONFIDENCE = {
    "high",
    "medium_high",
    "medium",
    "low",
}

ALLOWED_TARGET_GROUPS = {
    "men",
    "women",
    "unisex",
}


def error(message):
    errors.append(message)


def warning(message):
    warnings.append(message)


errors = []
warnings = []


# --------------------------------------------------
# 1. Load database
# --------------------------------------------------

if not DATABASE.exists():
    print(f"ERROR: Database not found: {DATABASE}")
    sys.exit(1)

try:
    data = json.loads(DATABASE.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    print(f"ERROR: Invalid JSON: {exc}")
    sys.exit(1)


products = data.get("products")

if not isinstance(products, list):
    print("ERROR: Top-level 'products' must be a list.")
    sys.exit(1)


print("SCENTAI DATA VALIDATOR")
print("=" * 50)
print(f"Schema version: {data.get('schema_version')}")
print(f"Products: {len(products)}")
print()


# --------------------------------------------------
# 2. Product IDs
# --------------------------------------------------

product_ids = [
    product.get("product_id")
    for product in products
]

missing_ids = [
    index
    for index, product_id in enumerate(product_ids)
    if not product_id
]

for index in missing_ids:
    error(f"Product at index {index} has no product_id.")

valid_ids = [
    product_id
    for product_id in product_ids
    if product_id
]

duplicates = [
    product_id
    for product_id, count in Counter(valid_ids).items()
    if count > 1
]

for product_id in duplicates:
    error(f"Duplicate product_id: {product_id}")

known_ids = set(valid_ids)


# --------------------------------------------------
# 3. Required fields
# --------------------------------------------------

required_top_level = [
    "product_id",
    "brand",
    "name",
    "concentration",
    "volume_ml",
    "classification",
    "community",
    "fragrance_profile",
    "market",
    "commercial",
    "relationships",
    "evidence",
    "validation",
]

for product in products:
    pid = product.get("product_id", "<UNKNOWN>")

    for field in required_top_level:
        if field not in product:
            error(f"{pid}: missing required field '{field}'")


# --------------------------------------------------
# 4. Individual product validation
# --------------------------------------------------

clusters = defaultdict(list)

for product in products:

    pid = product.get("product_id", "<UNKNOWN>")

    classification = product.get("classification", {})
    community = product.get("community", {})
    profile = product.get("fragrance_profile", {})
    scores = profile.get("scores", {})
    market = product.get("market", {})
    commercial = product.get("commercial", {})
    relationships = product.get("relationships", [])
    evidence = product.get("evidence", {})
    validation = product.get("validation", {})

    # ----------------------------------------------
    # Volume
    # ----------------------------------------------

    volume = product.get("volume_ml")

    if not isinstance(volume, (int, float)) or volume <= 0:
        error(f"{pid}: invalid volume_ml '{volume}'")

    # ----------------------------------------------
    # Classification
    # ----------------------------------------------

    role = classification.get("role")

    if role not in ALLOWED_ROLES:
        error(f"{pid}: invalid role '{role}'")

    cluster_id = classification.get("cluster_id")

    if not cluster_id:
        error(f"{pid}: missing cluster_id")
    else:
        clusters[cluster_id].append(product)

    target_groups = classification.get("scentai_target_groups")

    if not isinstance(target_groups, list) or not target_groups:
        error(f"{pid}: scentai_target_groups must be a non-empty list")
    else:
        for target in target_groups:
            if target not in ALLOWED_TARGET_GROUPS:
                error(
                    f"{pid}: invalid target group '{target}'"
                )

    # ----------------------------------------------
    # Community metrics
    # ----------------------------------------------

    community_values = [
        "rating_10",
        "longevity_10",
        "projection_10",
    ]

    for field in community_values:
        value = community.get(field)

        if value is None:
            warning(f"{pid}: community.{field} is missing")
            continue

        if not isinstance(value, (int, float)) or not 0 <= value <= 10:
            error(
                f"{pid}: community.{field} must be between 0 and 10"
            )

    rating_count = community.get("rating_count")

    if not isinstance(rating_count, int) or rating_count < 0:
        error(f"{pid}: invalid community rating_count")

    # ----------------------------------------------
    # SCENTAI profile scores
    # ----------------------------------------------

    profile_fields = [
        "freshness",
        "sweetness",
        "woodiness",
        "spiciness",
    ]

    for field in profile_fields:

        value = scores.get(field)

        if not isinstance(value, int) or not 1 <= value <= 10:
            error(
                f"{pid}: fragrance_profile.scores.{field} "
                f"must be integer 1-10"
            )

    score_confidence = profile.get("score_confidence")

    if score_confidence not in ALLOWED_CONFIDENCE:
        error(
            f"{pid}: invalid score_confidence "
            f"'{score_confidence}'"
        )

    # ----------------------------------------------
    # Market price calculation
    # ----------------------------------------------

    market_price = market.get("market_price_eur")
    stored_ppm = market.get("price_per_ml_eur")

    if market_price is None:
        error(f"{pid}: market_price_eur missing")

    elif not isinstance(market_price, (int, float)) or market_price <= 0:
        error(f"{pid}: invalid market_price_eur")

    if (
        isinstance(market_price, (int, float))
        and isinstance(volume, (int, float))
        and volume > 0
    ):

        calculated_ppm = market_price / volume

        if not isinstance(stored_ppm, (int, float)):
            error(f"{pid}: price_per_ml_eur missing")

        elif abs(calculated_ppm - stored_ppm) > 0.01:
            error(
                f"{pid}: price_per_ml mismatch "
                f"(stored={stored_ppm:.5f}, "
                f"calculated={calculated_ppm:.5f})"
            )

    # ----------------------------------------------
    # Commercial score boundaries
    # ----------------------------------------------

    universal_score_limits = {
        "retail_demand_proxy": 35,
        "community_demand": 20,
        "german_availability_score": 5,
        "monetization_potential": 5,
        "market_demand_score": 65,
    }

    for field, maximum in universal_score_limits.items():

        value = commercial.get(field)

        if not isinstance(value, int):
            error(
                f"{pid}: commercial.{field} must be an integer"
            )
            continue

        if not 0 <= value <= maximum:
            error(
                f"{pid}: commercial.{field}={value} "
                f"outside 0-{maximum}"
            )

    cluster_score_limits = {
        "alternative_demand": 20,
        "price_gap_score": 15,
        "cluster_opportunity_bonus": 35,
        "commercial_opportunity_score": 100,
    }

    cluster_values = [
        commercial.get(field)
        for field in cluster_score_limits
    ]

    if all(value is None for value in cluster_values):
        # Valid standalone product:
        # only the universal Market Demand Score applies.
        pass

    elif any(value is None for value in cluster_values):
        error(
            f"{pid}: cluster commercial scoring must be either "
            f"fully populated or fully N/A"
        )

    else:
        for field, maximum in cluster_score_limits.items():

            value = commercial.get(field)

            if not isinstance(value, int):
                error(
                    f"{pid}: commercial.{field} must be an integer "
                    f"or null for standalone products"
                )
                continue

            if not 0 <= value <= maximum:
                error(
                    f"{pid}: commercial.{field}={value} "
                    f"outside 0-{maximum}"
                )

    # ----------------------------------------------
    # Commercial score mathematics
    # ----------------------------------------------

    market_components = [
        commercial.get("retail_demand_proxy"),
        commercial.get("community_demand"),
        commercial.get("german_availability_score"),
        commercial.get("monetization_potential"),
    ]

    if all(isinstance(value, int) for value in market_components):

        calculated_market = sum(market_components)
        stored_market = commercial.get("market_demand_score")

        if stored_market != calculated_market:
            error(
                f"{pid}: market_demand_score mismatch "
                f"(stored={stored_market}, "
                f"calculated={calculated_market})"
            )

    cluster_components = [
        commercial.get("alternative_demand"),
        commercial.get("price_gap_score"),
    ]

    if all(isinstance(value, int) for value in cluster_components):

        calculated_cluster = sum(cluster_components)
        stored_cluster = commercial.get(
            "cluster_opportunity_bonus"
        )

        if stored_cluster != calculated_cluster:
            error(
                f"{pid}: cluster_opportunity_bonus mismatch "
                f"(stored={stored_cluster}, "
                f"calculated={calculated_cluster})"
            )

    market_score = commercial.get("market_demand_score")
    cluster_score = commercial.get("cluster_opportunity_bonus")
    total_score = commercial.get("commercial_opportunity_score")

    if (
        isinstance(market_score, int)
        and isinstance(cluster_score, int)
        and isinstance(total_score, int)
    ):

        calculated_total = market_score + cluster_score

        if total_score != calculated_total:
            error(
                f"{pid}: commercial_opportunity_score mismatch "
                f"(stored={total_score}, "
                f"calculated={calculated_total})"
            )

    # ----------------------------------------------
    # Relationships
    # ----------------------------------------------

    if not isinstance(relationships, list):
        error(f"{pid}: relationships must be a list")

    else:

        for relationship in relationships:

            related_id = relationship.get("related_product_id")

            if not related_id:
                error(
                    f"{pid}: relationship without related_product_id"
                )
                continue

            if related_id == pid:
                error(
                    f"{pid}: product cannot relate to itself"
                )

            if related_id not in known_ids:
                error(
                    f"{pid}: relationship references unknown product "
                    f"'{related_id}'"
                )

            relationship_type = relationship.get(
                "relationship_type"
            )

            if relationship_type not in {
                "clone",
                "inspired",
                "alternative",
            }:
                error(
                    f"{pid}: invalid relationship_type "
                    f"'{relationship_type}'"
                )

            confidence = relationship.get("confidence")

            if confidence not in ALLOWED_CONFIDENCE:
                error(
                    f"{pid}: invalid relationship confidence "
                    f"'{confidence}'"
                )

    # ----------------------------------------------
    # Evidence
    # ----------------------------------------------

    overall_confidence = evidence.get("overall")

    if overall_confidence not in ALLOWED_CONFIDENCE:
        error(
            f"{pid}: invalid evidence overall confidence "
            f"'{overall_confidence}'"
        )

    # ----------------------------------------------
    # Catalog readiness
    # ----------------------------------------------

    if validation.get("catalog_ready") is not True:
        warning(f"{pid}: catalog_ready is not true")


# --------------------------------------------------
# 5. Cluster validation
# --------------------------------------------------

for cluster_id, cluster_products in clusters.items():

    benchmarks = [
        product
        for product in cluster_products
        if product.get("classification", {}).get("role")
        == "benchmark"
    ]

    if len(benchmarks) == 0:
        warning(
            f"Cluster '{cluster_id}' has no benchmark"
        )


# --------------------------------------------------
# 6. Relationship reciprocity
# --------------------------------------------------

relationship_pairs = set()

for product in products:

    pid = product.get("product_id")

    for relationship in product.get("relationships", []):

        related_id = relationship.get("related_product_id")

        if pid and related_id:
            relationship_pairs.add((pid, related_id))


for source, target in sorted(relationship_pairs):

    if (target, source) not in relationship_pairs:
        warning(
            f"Relationship is one-way: "
            f"{source} -> {target}"
        )


# --------------------------------------------------
# 7. Final report
# --------------------------------------------------

print("Clusters:")
for cluster_id in sorted(clusters):
    print(
        f"  {cluster_id}: "
        f"{len(clusters[cluster_id])} products"
    )

print()

if warnings:
    print(f"WARNINGS: {len(warnings)}")

    for item in warnings:
        print(f"  WARNING: {item}")

    print()


if errors:

    print(f"ERRORS: {len(errors)}")

    for item in errors:
        print(f"  ERROR: {item}")

    print()
    print("VALIDATION FAILED")
    sys.exit(1)


print("ERRORS: 0")

if not warnings:
    print("WARNINGS: 0")

print()
print("VALIDATION PASSED")