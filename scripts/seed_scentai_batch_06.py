import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "examples" / "retail" / "data" / "scentai_products.json"


NEW_PRODUCTS = [
    {
        "product_id": "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100",
        "brand": "Essential Parfums",
        "name": "Bois Impérial",
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
        "release_year": 2020,
        "classification": {
            "official_orientation": "unisex",
            "community_category": "unisex",
            "scentai_target_groups": ["men", "women", "unisex"],
            "role": "benchmark",
            "cluster_id": "bois-imperial",
            "trend_bet": False,
        },
        "notes": {
            "top": ["Thai Basil", "Timut Pepper"],
            "heart": ["Haitian Vetiver"],
            "base": ["Georgywood", "Akigalawood"],
        },
        "community": {
            "source": "Parfumo",
            "rating_10": 8.1,
            "rating_count": 4385,
            "rank": 26,
            "rank_category": "unisex",
            "longevity_10": 8.5,
            "projection_10": 8.1,
        },
        "fragrance_profile": {
            "community_accords": ["fresh", "woody", "synthetic", "spicy", "green"],
            "scores": {"freshness": 8, "sweetness": 1, "woodiness": 9, "spiciness": 7},
            "score_confidence": "high",
        },
        "market": {
            "market_price_eur": 90.90,
            "price_per_ml_eur": 0.909,
            "german_availability": "high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-10",
        },
        "commercial": {
            "retail_demand_proxy": 27,
            "community_demand": 18,
            "german_availability_score": 5,
            "monetization_potential": 5,
            "market_demand_score": 55,
            "alternative_demand": 12,
            "price_gap_score": 7,
            "cluster_opportunity_bonus": 19,
            "commercial_opportunity_score": 74,
        },
        "relationships": [],
        "evidence": {
            "official_product_data": "high",
            "community_metrics": "high",
            "market_price": "high",
            "relationship_data": "medium",
            "overall": "high",
        },
        "validation": {"catalog_ready": True},
    },
    {
        "product_id": "SC-AL-AMBRA-DUBAI-MUSK-50",
        "brand": "Al Ambra",
        "name": "Dubai Musk",
        "concentration": "Extrait de Parfum",
        "volume_ml": 50,
        "release_year": None,
        "classification": {
            "official_orientation": "unisex",
            "community_category": "unisex",
            "scentai_target_groups": ["men", "women", "unisex"],
            "role": "benchmark",
            "cluster_id": "al-ambra-dubai-musk",
            "trend_bet": False,
        },
        "notes": {
            "top": [
                "White Magnolia",
                "Bergamot",
                "Indian Sandalwood",
                "Mandarin Orange",
                "Blackcurrant",
            ],
            "heart": ["White Musk"],
            "base": ["Pink Musk", "Indian Sandalwood"],
        },
        "community": {
            "source": "Parfumo",
            "rating_10": 8.5,
            "rating_count": 529,
            "rank": 318,
            "rank_category": "unisex",
            "longevity_10": 8.0,
            "projection_10": 7.5,
        },
        "fragrance_profile": {
            "community_accords": ["creamy", "fresh", "sweet", "citrus", "floral"],
            "scores": {"freshness": 7, "sweetness": 5, "woodiness": 4, "spiciness": 1},
            "score_confidence": "high",
        },
        "market": {
            "market_price_eur": 77.00,
            "price_per_ml_eur": 1.54,
            "german_availability": "medium",
            "price_source_count": 3,
            "price_checked_at": "2026-09-10",
        },
        "commercial": {
            "retail_demand_proxy": 20,
            "community_demand": 12,
            "german_availability_score": 3,
            "monetization_potential": 5,
            "market_demand_score": 40,
            "alternative_demand": 14,
            "price_gap_score": 10,
            "cluster_opportunity_bonus": 24,
            "commercial_opportunity_score": 64,
        },
        "relationships": [],
        "evidence": {
            "official_product_data": "high",
            "community_metrics": "high",
            "market_price": "medium_high",
            "relationship_data": "medium",
            "overall": "high",
        },
        "validation": {"catalog_ready": True},
    },
]


def main():
    with DB_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    products = data["products"]
    existing_ids = {product["product_id"] for product in products}

    added = []

    for product in NEW_PRODUCTS:
        if product["product_id"] in existing_ids:
            print(f"SKIP: {product['product_id']} ist bereits vorhanden.")
            continue

        products.append(product)
        existing_ids.add(product["product_id"])
        added.append(product["product_id"])

    with DB_PATH.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")

    print()
    print(f"Hinzugefügt: {len(added)}")

    for product_id in added:
        print(f"  + {product_id}")

    print()
    print(f"SCENTAI Produkte gesamt: {len(products)}")


if __name__ == "__main__":
    main()
