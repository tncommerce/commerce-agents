import json
from pathlib import Path


DATABASE = Path("examples/retail/data/scentai_products.json")


new_products = [
    {
        "product_id": "SC-PDM-LAYTON-125",
        "brand": "Parfums de Marly",
        "name": "Layton",
        "concentration": "Eau de Parfum",
        "volume_ml": 125,
        "release_year": 2016,

        "classification": {
            "official_orientation": "men",
            "community_category": "men",
            "scentai_target_groups": ["men"],
            "role": "benchmark",
            "cluster_id": "pdm-layton",
            "trend_bet": False
        },

        "notes": {
            "top": [
                "Apple",
                "Bergamot",
                "Cardamom"
            ],
            "heart": [
                "Lavender",
                "Violet",
                "Geranium"
            ],
            "base": [
                "Patchouli",
                "Vanilla",
                "Guaiac Wood",
                "Praline"
            ]
        },

        "community": {
            "source": "Parfumo",
            "rating_10": 8.6,
            "rating_count": 9051,
            "rank": 2,
            "rank_category": "men",
            "longevity_10": 8.2,
            "projection_10": 8.0
        },

        "fragrance_profile": {
            "community_accords": [
                "sweet",
                "spicy",
                "fruity",
                "woody",
                "oriental"
            ],
            "scores": {
                "freshness": 4,
                "sweetness": 9,
                "woodiness": 6,
                "spiciness": 8
            },
            "score_confidence": "high"
        },

        "market": {
            "official_price_eur": 290.0,
            "market_price_eur": 219.26,
            "price_per_ml_eur": 1.75408,
            "german_availability": "high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-09"
        },

        "commercial": {
            "retail_demand_proxy": 18,
            "community_demand": 20,
            "german_availability_score": 5,
            "monetization_potential": 3,
            "market_demand_score": 46,

            "alternative_demand": 20,
            "price_gap_score": 11,
            "cluster_opportunity_bonus": 31,

            "commercial_opportunity_score": 77,
            "score_status": "final_for_current_mvp_cluster"
        },

        "relationships": [
            {
                "related_product_id": "SC-AL-HARAMAIN-DETOUR-NOIR-100",
                "relationship_type": "clone",
                "confidence": "high"
            },
            {
                "related_product_id": "SC-ORIENTICA-ROYAL-BLEU-80",
                "relationship_type": "inspired",
                "confidence": "high"
            }
        ],

        "evidence": {
            "official_product_data": "high",
            "community_metrics": "high",
            "market_price": "high",
            "relationship_data": "high",
            "overall": "high"
        },

        "validation": {
            "catalog_ready": True
        }
    },

    {
        "product_id": "SC-AL-HARAMAIN-DETOUR-NOIR-100",
        "brand": "Al Haramain",
        "name": "Détour Noir",
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
        "release_year": None,

        "classification": {
            "official_orientation": "unisex",
            "community_category": "unisex",
            "scentai_target_groups": ["men", "unisex"],
            "role": "clone",
            "cluster_id": "pdm-layton",
            "trend_bet": False
        },

        "notes": {
            "top": [
                "Apple",
                "Lavender",
                "Violet",
                "Jasmine"
            ],
            "heart": [
                "Vanilla",
                "Patchouli",
                "Mandarin Orange",
                "Bergamot"
            ],
            "base": [
                "Cardamom",
                "Geranium",
                "Sandalwood",
                "Pepper",
                "Guaiac Wood"
            ]
        },

        "community": {
            "source": "Parfumo",
            "rating_10": 8.1,
            "rating_count": 2760,
            "rank": 64,
            "rank_category": "unisex",
            "longevity_10": 7.9,
            "projection_10": 7.6
        },

        "fragrance_profile": {
            "community_accords": [
                "sweet",
                "spicy",
                "fruity",
                "woody",
                "synthetic"
            ],
            "scores": {
                "freshness": 4,
                "sweetness": 9,
                "woodiness": 6,
                "spiciness": 8
            },
            "score_confidence": "high"
        },

        "market": {
            "market_price_eur": 19.95,
            "price_per_ml_eur": 0.1995,
            "german_availability": "high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-09"
        },

        "commercial": {
            "retail_demand_proxy": 18,
            "community_demand": 16,
            "german_availability_score": 5,
            "monetization_potential": 3,
            "market_demand_score": 42,

            "alternative_demand": 16,
            "price_gap_score": 15,
            "cluster_opportunity_bonus": 31,

            "commercial_opportunity_score": 73
        },

        "relationships": [
            {
                "related_product_id": "SC-PDM-LAYTON-125",
                "relationship_type": "clone",
                "confidence": "high"
            }
        ],

        "evidence": {
            "official_product_data": "high",
            "community_metrics": "high",
            "market_price": "high",
            "relationship_data": "high",
            "overall": "high"
        },

        "validation": {
            "catalog_ready": True
        }
    },

    {
        "product_id": "SC-ORIENTICA-ROYAL-BLEU-80",
        "brand": "Orientica",
        "name": "Royal Bleu",
        "concentration": "Eau de Parfum",
        "volume_ml": 80,
        "release_year": None,

        "classification": {
            "official_orientation": "unisex",
            "community_category": "unisex",
            "scentai_target_groups": ["men", "unisex"],
            "role": "inspired",
            "cluster_id": "pdm-layton",
            "trend_bet": False
        },

        "notes": {
            "top": [
                "Bergamot",
                "Lavender",
                "Mandarin",
                "Pepper",
                "Green Apple"
            ],
            "heart": [
                "Violet",
                "Jasmine",
                "Geranium",
                "Cardamom"
            ],
            "base": [
                "Patchouli",
                "Sandalwood",
                "Vanilla",
                "Musk",
                "Guaiac Wood"
            ]
        },

        "community": {
            "source": "Parfumo",
            "rating_10": 8.9,
            "rating_count": 198,
            "rank": None,
            "rank_category": "unisex",
            "longevity_10": 8.5,
            "projection_10": 8.2
        },

        "fragrance_profile": {
            "community_accords": [
                "sweet",
                "spicy",
                "oriental",
                "woody",
                "fruity"
            ],
            "scores": {
                "freshness": 4,
                "sweetness": 9,
                "woodiness": 6,
                "spiciness": 8
            },
            "score_confidence": "medium_high"
        },

        "market": {
            "market_price_eur": 69.95,
            "price_per_ml_eur": 0.874375,
            "german_availability": "medium",
            "price_source_count": 1,
            "price_checked_at": "2026-09-09"
        },

        "commercial": {
            "retail_demand_proxy": 12,
            "community_demand": 2,
            "german_availability_score": 3,
            "monetization_potential": 2,
            "market_demand_score": 19,

            "alternative_demand": 16,
            "price_gap_score": 9,
            "cluster_opportunity_bonus": 25,

            "commercial_opportunity_score": 44
        },

        "relationships": [
            {
                "related_product_id": "SC-PDM-LAYTON-125",
                "relationship_type": "inspired",
                "confidence": "high"
            }
        ],

        "evidence": {
            "official_product_data": "high",
            "community_metrics": "high",
            "market_price": "medium",
            "relationship_data": "high",
            "overall": "medium_high"
        },

        "validation": {
            "catalog_ready": True
        }
    },

    {
        "product_id": "SC-PDM-ALTHAIR-125",
        "brand": "Parfums de Marly",
        "name": "Althaïr",
        "concentration": "Eau de Parfum",
        "volume_ml": 125,
        "release_year": 2023,

        "classification": {
            "official_orientation": "men",
            "community_category": "men",
            "scentai_target_groups": ["men"],
            "role": "benchmark",
            "cluster_id": "pdm-althair",
            "trend_bet": False
        },

        "notes": {
            "top": [
                "Bergamot",
                "Mandarin",
                "Elemi"
            ],
            "heart": [
                "Orange Blossom",
                "Cinnamon",
                "Cardamom"
            ],
            "base": [
                "Bourbon Vanilla",
                "Guaiac Wood",
                "Praline"
            ]
        },

        "community": {
            "source": "Parfumo",
            "rating_10": 8.4,
            "rating_count": 5195,
            "rank": 9,
            "rank_category": "men",
            "longevity_10": 8.3,
            "projection_10": 8.1
        },

        "fragrance_profile": {
            "community_accords": [
                "sweet",
                "gourmand",
                "creamy",
                "spicy",
                "woody"
            ],
            "scores": {
                "freshness": 3,
                "sweetness": 10,
                "woodiness": 5,
                "spiciness": 6
            },
            "score_confidence": "high"
        },

        "market": {
            "official_price_eur": 290.0,
            "market_price_eur": 239.99,
            "price_per_ml_eur": 1.91992,
            "german_availability": "high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-09"
        },

        "commercial": {
            "retail_demand_proxy": 18,
            "community_demand": 20,
            "german_availability_score": 5,
            "monetization_potential": 3,
            "market_demand_score": 46,

            "alternative_demand": 20,
            "price_gap_score": 15,
            "cluster_opportunity_bonus": 35,

            "commercial_opportunity_score": 81,
            "score_status": "provisional_until_cluster_complete"
        },

        "relationships": [
            {
                "related_product_id": "SC-FRENCH-AVENUE-LIQUID-BRUN-100",
                "relationship_type": "clone",
                "confidence": "high"
            }
        ],

        "evidence": {
            "official_product_data": "high",
            "community_metrics": "high",
            "market_price": "high",
            "relationship_data": "high",
            "overall": "high"
        },

        "validation": {
            "catalog_ready": True
        }
    },

    {
        "product_id": "SC-FRENCH-AVENUE-LIQUID-BRUN-100",
        "brand": "French Avenue",
        "name": "Liquid Brun",
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
        "release_year": 2024,

        "classification": {
            "official_orientation": "men",
            "community_category": "unisex",
            "scentai_target_groups": ["men", "unisex"],
            "role": "clone",
            "cluster_id": "pdm-althair",
            "trend_bet": False
        },

        "notes": {
            "top": [
                "Cinnamon",
                "Bergamot",
                "Cardamom",
                "Orange Blossom"
            ],
            "heart": [
                "Bourbon Vanilla",
                "Elemi"
            ],
            "base": [
                "Musk",
                "Praline",
                "Ambroxan",
                "Guaiac Wood"
            ]
        },

        "community": {
            "source": "Parfumo",
            "rating_10": 8.4,
            "rating_count": 2327,
            "rank": 52,
            "rank_category": "unisex",
            "longevity_10": 8.4,
            "projection_10": 8.1
        },

        "fragrance_profile": {
            "community_accords": [
                "sweet",
                "gourmand",
                "creamy",
                "spicy",
                "oriental"
            ],
            "scores": {
                "freshness": 3,
                "sweetness": 10,
                "woodiness": 3,
                "spiciness": 6
            },
            "score_confidence": "high"
        },

        "market": {
            "market_price_eur": 24.70,
            "price_per_ml_eur": 0.247,
            "german_availability": "high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-09"
        },

        "commercial": {
            "retail_demand_proxy": 18,
            "community_demand": 15,
            "german_availability_score": 5,
            "monetization_potential": 3,
            "market_demand_score": 41,

            "alternative_demand": 20,
            "price_gap_score": 15,
            "cluster_opportunity_bonus": 35,

            "commercial_opportunity_score": 76
        },

        "relationships": [
            {
                "related_product_id": "SC-PDM-ALTHAIR-125",
                "relationship_type": "clone",
                "confidence": "high"
            }
        ],

        "evidence": {
            "official_product_data": "high",
            "community_metrics": "high",
            "market_price": "high",
            "relationship_data": "high",
            "overall": "high"
        },

        "validation": {
            "catalog_ready": True
        }
    }
]


data = json.loads(
    DATABASE.read_text(encoding="utf-8")
)

existing_ids = {
    product["product_id"]
    for product in data["products"]
}

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


DATABASE.write_text(
    json.dumps(
        data,
        indent=2,
        ensure_ascii=False
    ) + "\n",
    encoding="utf-8"
)


print()
print(f"Added: {added}")
print(f"Skipped: {skipped}")
print(f"Total products: {len(data['products'])}")