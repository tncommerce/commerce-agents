import json
from pathlib import Path

DATABASE = Path("examples/retail/data/scentai_products.json")


new_products = [
    {
        "product_id": "SC-XERJOFF-NAXOS-100",
        "brand": "Xerjoff",
        "name": "Naxos",
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
        "release_year": 2015,
        "classification": {
            "official_orientation": "unisex",
            "community_category": "unisex",
            "scentai_target_groups": ["men", "unisex"],
            "role": "benchmark",
            "cluster_id": "xerjoff-naxos",
            "trend_bet": False,
        },
        "notes": {
            "top": ["Lavender", "Bergamot", "Omani Frankincense", "Lemon"],
            "heart": ["Honey", "Jasmine Sambac", "Cashmere", "Cinnamon"],
            "base": ["Tobacco", "Tonka Bean", "Vanilla"],
        },
        "community": {
            "source": "Parfumo",
            "rating_10": 8.9,
            "rating_count": 13633,
            "rank": 1,
            "rank_category": "unisex",
            "longevity_10": 8.8,
            "projection_10": 8.5,
        },
        "fragrance_profile": {
            "community_accords": ["sweet", "spicy", "gourmand", "creamy", "citrus"],
            "scores": {"freshness": 6, "sweetness": 10, "woodiness": 2, "spiciness": 8},
            "score_confidence": "high",
        },
        "market": {
            "official_price_eur": 245.0,
            "market_price_eur": 141.03,
            "price_per_ml_eur": 1.4103,
            "german_availability": "high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-10",
        },
        "commercial": {
            "retail_demand_proxy": 24,
            "community_demand": 20,
            "german_availability_score": 5,
            "monetization_potential": 4,
            "market_demand_score": 53,
            "alternative_demand": 20,
            "price_gap_score": 13,
            "cluster_opportunity_bonus": 33,
            "commercial_opportunity_score": 86,
        },
        "relationships": [
            {
                "related_product_id": "SC-NUSUK-ATEEQ-100",
                "relationship_type": "inspired",
                "confidence": "high",
            },
            {
                "related_product_id": "SC-RAYHAAN-ITALIA-100",
                "relationship_type": "inspired",
                "confidence": "high",
            },
        ],
        "evidence": {
            "official_product_data": "high",
            "community_metrics": "high",
            "market_price": "high",
            "relationship_data": "high",
            "overall": "high",
        },
        "validation": {"catalog_ready": True},
    },
    {
        "product_id": "SC-NUSUK-ATEEQ-100",
        "brand": "Nusuk",
        "name": "Ateeq",
        "concentration": "Extrait de Parfum",
        "volume_ml": 100,
        "release_year": 2025,
        "classification": {
            "official_orientation": None,
            "community_category": "unisex",
            "scentai_target_groups": ["men", "unisex"],
            "role": "inspired",
            "cluster_id": "xerjoff-naxos",
            "trend_bet": False,
        },
        "notes": {
            "top": ["Honey", "Amber", "Cinnamon", "Grapefruit", "Lime"],
            "heart": ["Tobacco", "Lavender", "Jasmine"],
            "base": ["Tonka Bean", "Vanilla Orchid", "Coumarin", "Musk", "Cedarwood"],
        },
        "community": {
            "source": "Parfumo",
            "rating_10": 8.7,
            "rating_count": 647,
            "rank": 210,
            "rank_category": "unisex",
            "longevity_10": 8.6,
            "projection_10": 8.4,
        },
        "fragrance_profile": {
            "community_accords": ["sweet", "spicy", "gourmand", "creamy", "oriental"],
            "scores": {"freshness": 4, "sweetness": 10, "woodiness": 3, "spiciness": 8},
            "score_confidence": "high",
        },
        "market": {
            "market_price_eur": 28.85,
            "price_per_ml_eur": 0.2885,
            "german_availability": "high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-10",
        },
        "commercial": {
            "retail_demand_proxy": 18,
            "community_demand": 11,
            "german_availability_score": 5,
            "monetization_potential": 3,
            "market_demand_score": 37,
            "alternative_demand": 16,
            "price_gap_score": 13,
            "cluster_opportunity_bonus": 29,
            "commercial_opportunity_score": 66,
        },
        "relationships": [
            {
                "related_product_id": "SC-XERJOFF-NAXOS-100",
                "relationship_type": "inspired",
                "confidence": "high",
            }
        ],
        "evidence": {
            "official_product_data": "medium",
            "community_metrics": "high",
            "market_price": "high",
            "relationship_data": "high",
            "overall": "high",
        },
        "validation": {"catalog_ready": True},
    },
    {
        "product_id": "SC-RAYHAAN-ITALIA-100",
        "brand": "Rayhaan",
        "name": "Italia",
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
        "release_year": 2025,
        "classification": {
            "official_orientation": "men",
            "community_category": "men",
            "scentai_target_groups": ["men"],
            "role": "inspired",
            "cluster_id": "xerjoff-naxos",
            "trend_bet": False,
        },
        "notes": {
            "top": ["Lavender", "Bergamot", "Lemon"],
            "heart": ["Honey", "Cashmeran", "Jasmine Sambac", "Cinnamon"],
            "base": ["Tonka Bean", "Tobacco", "Vanilla"],
        },
        "community": {
            "source": "Parfumo",
            "rating_10": 8.5,
            "rating_count": 143,
            "rank": None,
            "rank_category": "men",
            "longevity_10": 8.1,
            "projection_10": 8.0,
        },
        "fragrance_profile": {
            "community_accords": ["sweet", "spicy", "creamy", "citrus", "gourmand"],
            "scores": {"freshness": 6, "sweetness": 10, "woodiness": 3, "spiciness": 8},
            "score_confidence": "medium_high",
        },
        "market": {
            "market_price_eur": 29.89,
            "price_per_ml_eur": 0.2989,
            "german_availability": "high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-10",
        },
        "commercial": {
            "retail_demand_proxy": 12,
            "community_demand": 2,
            "german_availability_score": 4,
            "monetization_potential": 2,
            "market_demand_score": 20,
            "alternative_demand": 12,
            "price_gap_score": 13,
            "cluster_opportunity_bonus": 25,
            "commercial_opportunity_score": 45,
        },
        "relationships": [
            {
                "related_product_id": "SC-XERJOFF-NAXOS-100",
                "relationship_type": "inspired",
                "confidence": "high",
            }
        ],
        "evidence": {
            "official_product_data": "medium",
            "community_metrics": "high",
            "market_price": "medium_high",
            "relationship_data": "high",
            "overall": "medium_high",
        },
        "validation": {"catalog_ready": True},
    },
    {
        "product_id": "SC-DIOR-HOMME-INTENSE-100",
        "brand": "Dior",
        "name": "Dior Homme Intense",
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
        "release_year": 2011,
        "classification": {
            "official_orientation": "men",
            "community_category": "men",
            "scentai_target_groups": ["men"],
            "role": "benchmark",
            "cluster_id": "dior-homme-intense",
            "trend_bet": False,
        },
        "notes": {"key": ["Iris", "Ambrette Seed", "Woody Notes"]},
        "community": {
            "source": "Parfumo",
            "rating_10": 8.5,
            "rating_count": 8741,
            "rank": 3,
            "rank_category": "men",
            "longevity_10": 8.2,
            "projection_10": 7.9,
        },
        "fragrance_profile": {
            "community_accords": ["powdery", "sweet", "woody", "spicy", "creamy"],
            "scores": {"freshness": 2, "sweetness": 8, "woodiness": 7, "spiciness": 6},
            "score_confidence": "high",
        },
        "market": {
            "official_price_eur": 148.0,
            "market_price_eur": 95.0,
            "price_per_ml_eur": 0.95,
            "german_availability": "very_high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-10",
        },
        "commercial": {
            "retail_demand_proxy": 24,
            "community_demand": 20,
            "german_availability_score": 5,
            "monetization_potential": 5,
            "market_demand_score": 54,
            "alternative_demand": 16,
            "price_gap_score": 13,
            "cluster_opportunity_bonus": 29,
            "commercial_opportunity_score": 83,
        },
        "relationships": [
            {
                "related_product_id": "SC-AL-WATANIAH-KAYAAN-CLASSIC-100",
                "relationship_type": "clone",
                "confidence": "high",
            }
        ],
        "evidence": {
            "official_product_data": "high",
            "community_metrics": "high",
            "market_price": "high",
            "relationship_data": "high",
            "overall": "high",
        },
        "validation": {"catalog_ready": True},
    },
    {
        "product_id": "SC-AL-WATANIAH-KAYAAN-CLASSIC-100",
        "brand": "Al Wataniah",
        "name": "Kayaan Classic",
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
        "release_year": None,
        "classification": {
            "official_orientation": None,
            "community_category": "unisex",
            "scentai_target_groups": ["men", "unisex"],
            "role": "clone",
            "cluster_id": "dior-homme-intense",
            "trend_bet": False,
        },
        "notes": {
            "top": ["Pale Iris", "Italian Orange"],
            "heart": ["Leather", "Rose"],
            "base": ["Ambrette", "Cedar", "Sandalwood", "Oud"],
        },
        "community": {
            "source": "Parfumo",
            "rating_10": 8.8,
            "rating_count": 574,
            "rank": 241,
            "rank_category": "unisex",
            "longevity_10": 7.5,
            "projection_10": 7.3,
        },
        "fragrance_profile": {
            "community_accords": ["powdery", "sweet", "woody", "floral", "creamy"],
            "scores": {"freshness": 2, "sweetness": 8, "woodiness": 7, "spiciness": 2},
            "score_confidence": "high",
        },
        "market": {
            "market_price_eur": 19.50,
            "price_per_ml_eur": 0.195,
            "german_availability": "high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-10",
        },
        "commercial": {
            "retail_demand_proxy": 18,
            "community_demand": 11,
            "german_availability_score": 5,
            "monetization_potential": 4,
            "market_demand_score": 38,
            "alternative_demand": 16,
            "price_gap_score": 13,
            "cluster_opportunity_bonus": 29,
            "commercial_opportunity_score": 67,
        },
        "relationships": [
            {
                "related_product_id": "SC-DIOR-HOMME-INTENSE-100",
                "relationship_type": "clone",
                "confidence": "high",
            }
        ],
        "evidence": {
            "official_product_data": "medium_high",
            "community_metrics": "high",
            "market_price": "high",
            "relationship_data": "high",
            "overall": "high",
        },
        "validation": {"catalog_ready": True},
    },
]


data = json.loads(DATABASE.read_text(encoding="utf-8"))

existing_ids = {product["product_id"] for product in data["products"]}

added = 0
skipped = 0

for product in new_products:
    if product["product_id"] in existing_ids:
        print(f"SKIP: {product['product_id']}")
        skipped += 1
        continue

    data["products"].append(product)
    existing_ids.add(product["product_id"])

    print(f"ADD:  {product['product_id']}")
    added += 1


DATABASE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


print()
print(f"Added: {added}")
print(f"Skipped: {skipped}")
print(f"Total products: {len(data['products'])}")
