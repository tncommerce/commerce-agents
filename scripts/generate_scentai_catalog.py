import json
from pathlib import Path


SOURCE_DATABASE = Path(
    "examples/retail/data/scentai_products.json"
)

CURRENT_CATALOG = Path(
    "examples/retail/data/catalog.json"
)

OUTPUT_CATALOG = Path(
    "examples/retail/data/catalog.scentai-preview.json"
)

LEGACY_SCENTAI_IDS = {
    "SC-0001",
    "SC-0002",
    "SC-0003",
}


def as_string(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def join_values(values):
    if not values:
        return ""
    return ", ".join(str(value) for value in values)


def build_product_name_map(products):
    return {
        product["product_id"]:
        f"{product['brand']} {product['name']}"
        for product in products
    }


def build_short_description(product):
    brand = product["brand"]
    name = product["name"]
    concentration = product["concentration"]

    accords = product.get(
        "fragrance_profile", {}
    ).get(
        "community_accords", []
    )

    if accords:
        main_accords = ", ".join(accords[:3])

        return (
            f"{brand} {name} is a "
            f"{main_accords} "
            f"{concentration} fragrance."
        )

    return (
        f"{brand} {name} "
        f"{concentration} fragrance."
    )


def convert_product(product, product_name_map):
    community = product["community"]
    profile = product["fragrance_profile"]
    scores = profile["scores"]
    market = product["market"]
    classification = product["classification"]
    evidence = product["evidence"]

    rating_10 = community["rating_10"]

    # Anthropic demo catalog expects a rating
    # on a maximum 5-star scale.
    #
    # Customer-facing SCENTAI ratings continue
    # to use community_rating_10 from Parfumo.
    internal_rating_5 = round(rating_10 / 2, 1)

    related_names = []

    for relationship in product.get(
        "relationships", []
    ):
        related_id = relationship.get(
            "related_product_id"
        )

        related_name = product_name_map.get(
            related_id
        )

        if related_name:
            related_names.append(related_name)

    target_groups = classification.get(
        "scentai_target_groups", []
    )

    labels = []

    for accord in profile.get(
        "community_accords", []
    )[:5]:
        if accord not in labels:
            labels.append(accord)

    role = classification.get("role")

    if role and role not in labels:
        labels.append(role)

    if classification.get("trend_bet"):
        labels.append("trend-bet")

    title = (
        f"{product['brand']} "
        f"{product['name']} "
        f"{product['concentration']} "
        f"{product['volume_ml']} ml"
    )

    attributes = {
        "canonical_name":
    as_string(product["name"]),
        "community_rating_10":
            as_string(community["rating_10"]),

        "rating_source":
            as_string(community.get("source")),

        "volume_ml":
            as_string(product["volume_ml"]),

        "concentration":
            as_string(product["concentration"]),

        "target_group":
            join_values(target_groups),

        "main_accords":
            join_values(
                profile.get(
                    "community_accords", []
                )
            ),

        "freshness":
            as_string(scores["freshness"]),

        "sweetness":
            as_string(scores["sweetness"]),

        "woodiness":
            as_string(scores["woodiness"]),

        "spiciness":
            as_string(scores["spiciness"]),

        "longevity":
            as_string(
                community.get("longevity_10")
            ),

        "projection":
            as_string(
                community.get("projection_10")
            ),

        "cluster_id":
            as_string(
                classification.get(
                    "cluster_id"
                )
            ),

        "relationship_role":
            as_string(
                classification.get("role")
            ),

        "trend_bet":
            as_string(
                classification.get(
                    "trend_bet", False
                )
            ),

        "similar_to":
            join_values(related_names),

        "evidence_confidence":
            as_string(
                evidence.get("overall")
            ),

        "market_price_eur":
            as_string(
                market.get(
                    "market_price_eur"
                )
            ),

        "price_per_ml_eur":
            as_string(
                market.get(
                    "price_per_ml_eur"
                )
            ),

        "price_checked_at":
            as_string(
                market.get(
                    "price_checked_at"
                )
            ),
    }

    return {
        "product_id":
            product["product_id"],

        "title":
            title,

        "image_url":
            product.get("image_url"),

        "brand":
            product["brand"],

        "price":
            market["market_price_eur"],

        "currency":
            "EUR",

        "rating":
            internal_rating_5,

        "review_count":
            community["rating_count"],

        "category":
            "fragrance",

        "labels":
            labels,

        "attributes":
            attributes,

        # Local MVP/demo catalog availability.
        # This is not live retailer inventory.
        "in_stock":
            True,

        "short_description":
            build_short_description(product),
    }


def main():
    source = json.loads(
        SOURCE_DATABASE.read_text(
            encoding="utf-8"
        )
    )

    current_catalog = json.loads(
        CURRENT_CATALOG.read_text(
            encoding="utf-8"
        )
    )

    scentai_products = source["products"]

    name_map = build_product_name_map(
        scentai_products
    )

    generated_products = [
        convert_product(
            product,
            name_map
        )
        for product in scentai_products
    ]

    new_ids = {
        product["product_id"]
        for product in generated_products
    }

    preserved_products = []

    removed_legacy = 0
    removed_existing_generated = 0

    for product in current_catalog.get(
        "products", []
    ):
        product_id = product.get(
            "product_id"
        )

        if product_id in LEGACY_SCENTAI_IDS:
            removed_legacy += 1
            continue

        if product_id in new_ids:
            removed_existing_generated += 1
            continue

        preserved_products.append(product)

    output = {
        "store_name": "SCENTAI",
        "products":
            generated_products
            + preserved_products,
    }

    OUTPUT_CATALOG.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False
        ) + "\n",
        encoding="utf-8",
    )

    print("SCENTAI CATALOG GENERATOR")
    print("=" * 50)

    print(
        f"Source SCENTAI products: "
        f"{len(scentai_products)}"
    )

    print(
        f"Legacy SCENTAI products removed: "
        f"{removed_legacy}"
    )

    print(
        f"Existing generated products replaced: "
        f"{removed_existing_generated}"
    )

    print(
        f"Demo products preserved: "
        f"{len(preserved_products)}"
    )

    print(
        f"Final preview products: "
        f"{len(output['products'])}"
    )

    print()
    print(
        f"Preview written to:"
    )
    print(OUTPUT_CATALOG)


if __name__ == "__main__":
    main()