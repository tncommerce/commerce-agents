import json
from pathlib import Path


DATABASE = Path("examples/retail/data/scentai_products.json")


new_products = [
    {
        "product_id": "SC-BVLGARI-TYGAR-125",
        "brand": "Bvlgari",
        "name": "Le Gemme Tygar",
        "concentration": "Eau de Parfum",
        "volume_ml": 125,
        "release_year": 2016,

        "classification": {
            "official_orientation": "unisex",
            "community_category": "unisex",
            "scentai_target_groups": ["men", "unisex"],
            "role": "benchmark",
            "cluster_id": "tygar-vibrato",
            "trend_bet": False
        },

        "notes": {
            "key": [
                "Grapefruit",
                "Ambergris"
            ]
        },

        "community": {
            "source": "Parfumo",
            "rating_10": 8.5,
            "rating_count": 998,
            "rank": 153,
            "rank_category": "unisex",
            "longevity_10": 7.7,
            "projection_10": 7.5
        },

        "fragrance_profile": {
            "community_accords": [
                "citrus",
                "fresh",
                "woody",
                "spicy",
                "fruity"
            ],
            "scores": {
                "freshness": 10,
                "sweetness": 2,
                "woodiness": 7,
                "spiciness": 6
            },
            "score_confidence": "high"
        },

        "market": {
            "official_price_eur": 389.0,
            "market_price_eur": 311.20,
            "price_per_ml_eur": 2.4896,
            "german_availability": "high",
            "price_source_count": 2,
            "price_checked_at": "2026-09-09"
        },

        "commercial": {
            "retail_demand_proxy": 18,
            "community_demand": 11,
            "german_availability_score": 5,
            "monetization_potential": 4,
            "market_demand_score": 38,

            "alternative_demand": 20,
            "price_gap_score": 15,
            "cluster_opportunity_bonus": 35,

            "commercial_opportunity_score": 73
        },

        "relationships": [
            {
                "related_product_id": "SC-SOSPIRO-VIBRATO-100",
                "relationship_type": "alternative",
                "confidence": "high"
            },
            {
                "related_product_id": "SC-AFNAN-TURATHI-BLUE-90",
                "relationship_type": "inspired",
                "confidence": "high"
            },
            {
                "related_product_id": "SC-MAISON-ASRAR-REGENT-100",
                "relationship_type": "inspired",
                "confidence": "medium_high"
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
        "product_id": "SC-SOSPIRO-VIBRATO-100",
        "brand": "Sospiro",
        "name": "Vibrato",
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
        "release_year": 2022,

        "classification": {
            "official_orientation": "unisex",
            "community_category": "unisex",
            "scentai_target_groups": ["men", "unisex"],
            "role": "benchmark",
            "cluster_id": "tygar-vibrato",
            "trend_bet": False
        },

        "notes": {
            "top": [
                "Grapefruit",
                "Ginger",
                "Bergamot",
                "Mandarin",
                "Rosemary"
            ],
            "heart": [
                "Light Woods",
                "Magnolia",
                "Damask Rose"
            ],
            "base": [
                "Crystal Amber",
                "Musk",
                "Sandalwood",
                "Patchouli",
                "Tonka Bean",
                "Vetiver"
            ]
        },

        "community": {
            "source": "Parfumo",
            "rating_10": 8.7,
            "rating_count": 2464,
            "rank": 25,
            "rank_category": "unisex",
            "longevity_10": 8.2,
            "projection_10": 8.0
        },

        "fragrance_profile": {
            "community_accords": [
                "citrus",
                "fresh",
                "fruity",
                "woody",
                "floral"
            ],
            "scores": {
                "freshness": 10,
                "sweetness": 3,
                "woodiness": 6,
                "spiciness": 3
            },
            "score_confidence": "high"
        },

        "market": {
            "market_price_eur": 229.99,
            "price_per_ml_eur": 2.2999,
            "german_availability": "high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-09"
        },

        "commercial": {
            "retail_demand_proxy": 18,
            "community_demand": 17,
            "german_availability_score": 5,
            "monetization_potential": 3,
            "market_demand_score": 43,

            "alternative_demand": 20,
            "price_gap_score": 15,
            "cluster_opportunity_bonus": 35,

            "commercial_opportunity_score": 78
        },

        "relationships": [
            {
                "related_product_id": "SC-BVLGARI-TYGAR-125",
                "relationship_type": "alternative",
                "confidence": "high"
            },
            {
                "related_product_id": "SC-AFNAN-TURATHI-BLUE-90",
                "relationship_type": "inspired",
                "confidence": "high"
            },
            {
                "related_product_id": "SC-MAISON-ASRAR-REGENT-100",
                "relationship_type": "inspired",
                "confidence": "high"
            }
        ],

        "evidence": {
            "official_product_data": "medium_high",
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
        "product_id": "SC-AFNAN-TURATHI-BLUE-90",
        "brand": "Afnan Perfumes",
        "name": "Turathi Blue",
        "concentration": "Eau de Parfum",
        "volume_ml": 90,
        "release_year": None,

        "classification": {
            "official_orientation": "men",
            "community_category": "men",
            "scentai_target_groups": ["men"],
            "role": "inspired",
            "cluster_id": "tygar-vibrato",
            "trend_bet": False
        },

        "notes": {
            "top": [
                "Mandarin",
                "Bergamot"
            ],
            "heart": [
                "Amber",
                "Woody Notes"
            ],
            "base": [
                "Musk",
                "Spices",
                "Patchouli"
            ]
        },

        "community": {
            "source": "Parfumo",
            "rating_10": 8.1,
            "rating_count": 3874,
            "rank": 26,
            "rank_category": "men",
            "longevity_10": 7.6,
            "projection_10": 7.4
        },

        "fragrance_profile": {
            "community_accords": [
                "citrus",
                "fresh",
                "fruity",
                "woody",
                "aquatic"
            ],
            "scores": {
                "freshness": 10,
                "sweetness": 3,
                "woodiness": 6,
                "spiciness": 4
            },
            "score_confidence": "high"
        },

        "market": {
            "market_price_eur": 30.31,
            "price_per_ml_eur": 0.33678,
            "german_availability": "high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-09"
        },

        "commercial": {
            "retail_demand_proxy": 18,
            "community_demand": 17,
            "german_availability_score": 5,
            "monetization_potential": 3,
            "market_demand_score": 43,

            "alternative_demand": 20,
            "price_gap_score": 15,
            "cluster_opportunity_bonus": 35,

            "commercial_opportunity_score": 78
        },

        "relationships": [
            {
                "related_product_id": "SC-BVLGARI-TYGAR-125",
                "relationship_type": "inspired",
                "confidence": "high"
            },
            {
                "related_product_id": "SC-SOSPIRO-VIBRATO-100",
                "relationship_type": "inspired",
                "confidence": "high"
            }
        ],

        "evidence": {
            "official_product_data": "medium_high",
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
        "product_id": "SC-MAISON-ASRAR-REGENT-100",
        "brand": "Maison Asrar",
        "name": "Regent",
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
        "release_year": 2026,

        "classification": {
            "official_orientation": "unisex",
            "community_category": "unisex",
            "scentai_target_groups": ["men", "unisex"],
            "role": "inspired",
            "cluster_id": "tygar-vibrato",
            "trend_bet": True
        },

        "notes": {
            "top": [
                "Bergamot",
                "Grapefruit",
                "Ginger",
                "Mandarin"
            ],
            "heart": [
                "Orris Root",
                "Jasmine",
                "Orange Blossom"
            ],
            "base": [
                "Amber",
                "Musk",
                "Patchouli",
                "Sandalwood",
                "Tonka Bean",
                "Cedarwood"
            ]
        },

        "community": {
            "source": "Parfumo",
            "rating_10": 8.5,
            "rating_count": 72,
            "rank": None,
            "rank_category": "unisex",
            "longevity_10": 7.2,
            "projection_10": 7.0
        },

        "fragrance_profile": {
            "community_accords": [
                "citrus",
                "fresh",
                "floral",
                "woody",
                "fruity"
            ],
            "scores": {
                "freshness": 10,
                "sweetness": 3,
                "woodiness": 6,
                "spiciness": 4
            },
            "score_confidence": "medium_high"
        },

        "market": {
            "market_price_eur": 43.99,
            "price_per_ml_eur": 0.4399,
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
            "price_gap_score": 15,
            "cluster_opportunity_bonus": 31,

            "commercial_opportunity_score": 50
        },

        "relationships": [
            {
                "related_product_id": "SC-BVLGARI-TYGAR-125",
                "relationship_type": "inspired",
                "confidence": "medium_high"
            },
            {
                "related_product_id": "SC-SOSPIRO-VIBRATO-100",
                "relationship_type": "inspired",
                "confidence": "high"
            }
        ],

        "evidence": {
            "official_product_data": "medium_high",
            "community_metrics": "medium",
            "market_price": "medium",
            "relationship_data": "medium_high",
            "overall": "medium_high"
        },

        "validation": {
            "catalog_ready": True
        }
    },

    {
        "product_id": "SC-ARMANI-SWY-INTENSELY-100",
        "brand": "Giorgio Armani",
        "name": "Stronger With You Intensely",
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
        "release_year": 2018,

        "classification": {
            "official_orientation": "men",
            "community_category": "men",
            "scentai_target_groups": ["men"],
            "role": "benchmark",
            "cluster_id": "armani-swy-intensely",
            "trend_bet": False
        },

        "notes": {
            "top": [
                "Chestnut",
                "Pink Pepper"
            ],
            "heart": [
                "Lavender",
                "Sage"
            ],
            "base": [
                "Vanilla",
                "Amberwood"
            ]
        },

        "community": {
            "source": "Parfumo",
            "rating_10": 8.3,
            "rating_count": 5058,
            "rank": 12,
            "rank_category": "men",
            "longevity_10": 8.3,
            "projection_10": 8.1
        },

        "fragrance_profile": {
            "community_accords": [
                "sweet",
                "gourmand",
                "spicy",
                "oriental",
                "woody"
            ],
            "scores": {
                "freshness": 2,
                "sweetness": 10,
                "woodiness": 5,
                "spiciness": 7
            },
            "score_confidence": "high"
        },

        "market": {
            "market_price_eur": 66.04,
            "price_per_ml_eur": 0.6604,
            "german_availability": "very_high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-09"
        },

        "commercial": {
            "retail_demand_proxy": 35,
            "community_demand": 19,
            "german_availability_score": 5,
            "monetization_potential": 5,
            "market_demand_score": 64,

            "alternative_demand": None,
            "price_gap_score": None,
            "cluster_opportunity_bonus": None,
            "commercial_opportunity_score": None
        },

        "relationships": [],

        "evidence": {
            "official_product_data": "medium_high",
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