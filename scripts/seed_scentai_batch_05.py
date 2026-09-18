import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "examples" / "retail" / "data" / "scentai_products.json"


NEW_PRODUCTS = [
    {
        "product_id": "SC-VALENTINO-BORN-IN-ROMA-INTENSE-100",
        "brand": "Valentino",
        "name": "Uomo Born In Roma Intense",
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
        "release_year": 2023,
        "classification": {
            "official_orientation": None,
            "community_category": "men",
            "scentai_target_groups": ["men"],
            "role": "benchmark",
            "cluster_id": "valentino-born-in-roma-intense",
            "trend_bet": False,
        },
        "notes": {
            "top": ["Vanilla", "Ginger"],
            "heart": ["Provençal Lavender", "Nutmeg"],
            "base": ["Haitian Vetiver"],
        },
        "community": {
            "source": "Parfumo",
            "rating_10": 7.9,
            "rating_count": 1113,
            "rank": 171,
            "rank_category": "men",
            "longevity_10": 7.5,
            "projection_10": 7.3,
        },
        "fragrance_profile": {
            "community_accords": ["sweet", "synthetic", "fresh", "woody", "fruity"],
            "scores": {"freshness": 5, "sweetness": 8, "woodiness": 5, "spiciness": 5},
            "score_confidence": "high",
        },
        "market": {
            "market_price_eur": 66.0,
            "price_per_ml_eur": 0.66,
            "german_availability": "high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-10",
        },
        "commercial": {
            "retail_demand_proxy": 28,
            "community_demand": 14,
            "german_availability_score": 5,
            "monetization_potential": 5,
            "market_demand_score": 52,
            "alternative_demand": 8,
            "price_gap_score": 4,
            "cluster_opportunity_bonus": 12,
            "commercial_opportunity_score": 64,
        },
        "relationships": [],
        "evidence": {
            "official_product_data": "high",
            "community_metrics": "high",
            "market_price": "high",
            "relationship_data": "medium_high",
            "overall": "high",
        },
        "validation": {"catalog_ready": True},
    },
    {
        "product_id": "SC-CLIVE-CHRISTIAN-HEDONISTIC-50",
        "brand": "Clive Christian",
        "name": "Jump Up and Kiss Me Hedonistic",
        "concentration": "Parfum",
        "volume_ml": 50,
        "release_year": 2017,
        "classification": {
            "official_orientation": None,
            "community_category": "men",
            "scentai_target_groups": ["men"],
            "role": "benchmark",
            "cluster_id": "clive-christian-hedonistic",
            "trend_bet": False,
        },
        "notes": {
            "top": ["Black Cherry", "Clary Sage", "Bergamot", "Grapefruit", "Maté", "Neroli"],
            "heart": [
                "Absinthe Wormwood",
                "Iris",
                "Opium",
                "Cocoa Leaf",
                "Jasmine",
                "Papyrus",
                "Tobacco",
            ],
            "base": ["Amber", "Leather", "Labdanum", "Tonka Bean", "Vanilla"],
        },
        "community": {
            "source": "Parfumo",
            "rating_10": 8.9,
            "rating_count": 1789,
            "rank": 28,
            "rank_category": "men",
            "longevity_10": 8.4,
            "projection_10": 8.1,
        },
        "fragrance_profile": {
            "community_accords": ["sweet", "fruity", "spicy", "woody", "floral"],
            "scores": {"freshness": 2, "sweetness": 8, "woodiness": 6, "spiciness": 7},
            "score_confidence": "high",
        },
        "market": {
            "market_price_eur": 365.0,
            "price_per_ml_eur": 7.3,
            "german_availability": "medium",
            "price_source_count": 3,
            "price_checked_at": "2026-09-10",
        },
        "commercial": {
            "retail_demand_proxy": 10,
            "community_demand": 18,
            "german_availability_score": 2,
            "monetization_potential": 3,
            "market_demand_score": 33,
            "alternative_demand": 6,
            "price_gap_score": 15,
            "cluster_opportunity_bonus": 21,
            "commercial_opportunity_score": 54,
        },
        "relationships": [],
        "evidence": {
            "official_product_data": "medium_high",
            "community_metrics": "high",
            "market_price": "medium_high",
            "relationship_data": "medium_high",
            "overall": "high",
        },
        "validation": {"catalog_ready": True},
    },
    {
        "product_id": "SC-CHANEL-BLEU-DE-CHANEL-EDP-100",
        "brand": "Chanel",
        "name": "Bleu de Chanel",
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
        "release_year": 2014,
        "classification": {
            "official_orientation": None,
            "community_category": "men",
            "scentai_target_groups": ["men"],
            "role": "benchmark",
            "cluster_id": "bleu-de-chanel-edp",
            "trend_bet": False,
        },
        "notes": {
            "top": ["Mint", "Grapefruit", "Pink Pepper", "Lemon", "Coriander", "Aldehydes"],
            "heart": ["Nutmeg", "Ginger", "Jasmine", "Melon"],
            "base": [
                "Sandalwood",
                "Vetiver",
                "Incense",
                "Patchouli",
                "Cedar",
                "Labdanum",
                "Ambergris",
            ],
        },
        "community": {
            "source": "Parfumo",
            "rating_10": 8.2,
            "rating_count": 5751,
            "rank": 11,
            "rank_category": "men",
            "longevity_10": 7.3,
            "projection_10": 7.1,
        },
        "fragrance_profile": {
            "community_accords": ["fresh", "citrus", "woody", "spicy", "aquatic"],
            "scores": {"freshness": 8, "sweetness": 3, "woodiness": 7, "spiciness": 5},
            "score_confidence": "high",
        },
        "market": {
            "market_price_eur": 80.99,
            "price_per_ml_eur": 0.8099,
            "german_availability": "high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-10",
        },
        "commercial": {
            "retail_demand_proxy": 34,
            "community_demand": 19,
            "german_availability_score": 5,
            "monetization_potential": 5,
            "market_demand_score": 63,
            "alternative_demand": 15,
            "price_gap_score": 8,
            "cluster_opportunity_bonus": 23,
            "commercial_opportunity_score": 86,
        },
        "relationships": [],
        "evidence": {
            "official_product_data": "medium_high",
            "community_metrics": "high",
            "market_price": "high",
            "relationship_data": "medium_high",
            "overall": "high",
        },
        "validation": {"catalog_ready": True},
    },
    {
        "product_id": "SC-DIOR-SAUVAGE-EDP-100",
        "brand": "Dior",
        "name": "Sauvage",
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
        "release_year": 2018,
        "classification": {
            "official_orientation": None,
            "community_category": "men",
            "scentai_target_groups": ["men"],
            "role": "benchmark",
            "cluster_id": "dior-sauvage-edp",
            "trend_bet": False,
        },
        "notes": {
            "top": ["Bergamot", "Mandarin", "Citrus"],
            "heart": ["Sandalwood", "Cedar", "Vanilla"],
            "base": ["Tonka Bean", "Bergamot", "Ambroxan", "Vanilla"],
        },
        "community": {
            "source": "Parfumo",
            "rating_10": 7.8,
            "rating_count": 3286,
            "rank": 54,
            "rank_category": "men",
            "longevity_10": 8.0,
            "projection_10": 7.8,
        },
        "fragrance_profile": {
            "community_accords": ["fresh", "spicy", "synthetic", "citrus", "woody"],
            "scores": {"freshness": 8, "sweetness": 4, "woodiness": 6, "spiciness": 7},
            "score_confidence": "high",
        },
        "market": {
            "market_price_eur": 82.8,
            "price_per_ml_eur": 0.828,
            "german_availability": "high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-10",
        },
        "commercial": {
            "retail_demand_proxy": 35,
            "community_demand": 18,
            "german_availability_score": 5,
            "monetization_potential": 5,
            "market_demand_score": 63,
            "alternative_demand": 17,
            "price_gap_score": 8,
            "cluster_opportunity_bonus": 25,
            "commercial_opportunity_score": 88,
        },
        "relationships": [],
        "evidence": {
            "official_product_data": "medium_high",
            "community_metrics": "high",
            "market_price": "high",
            "relationship_data": "medium_high",
            "overall": "high",
        },
        "validation": {"catalog_ready": True},
    },
    {
        "product_id": "SC-PRADA-LHOMME-100",
        "brand": "Prada",
        "name": "L'Homme",
        "concentration": "Eau de Toilette",
        "volume_ml": 100,
        "release_year": 2016,
        "classification": {
            "official_orientation": None,
            "community_category": "men",
            "scentai_target_groups": ["men"],
            "role": "benchmark",
            "cluster_id": "prada-lhomme",
            "trend_bet": False,
        },
        "notes": {
            "top": ["Pepper", "Neroli"],
            "heart": ["Iris", "Violet", "Geranium", "Amber"],
            "base": ["Patchouli", "Cedar"],
        },
        "community": {
            "source": "Parfumo",
            "rating_10": 8.4,
            "rating_count": 7884,
            "rank": 5,
            "rank_category": "men",
            "longevity_10": 7.4,
            "projection_10": 7.1,
        },
        "fragrance_profile": {
            "community_accords": ["powdery", "fresh", "floral", "sweet", "creamy"],
            "scores": {"freshness": 7, "sweetness": 4, "woodiness": 5, "spiciness": 3},
            "score_confidence": "high",
        },
        "market": {
            "market_price_eur": 74.62,
            "price_per_ml_eur": 0.7462,
            "german_availability": "high",
            "price_source_count": 3,
            "price_checked_at": "2026-09-10",
        },
        "commercial": {
            "retail_demand_proxy": 29,
            "community_demand": 20,
            "german_availability_score": 5,
            "monetization_potential": 5,
            "market_demand_score": 59,
            "alternative_demand": 10,
            "price_gap_score": 7,
            "cluster_opportunity_bonus": 17,
            "commercial_opportunity_score": 76,
        },
        "relationships": [],
        "evidence": {
            "official_product_data": "medium_high",
            "community_metrics": "high",
            "market_price": "high",
            "relationship_data": "medium_high",
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
