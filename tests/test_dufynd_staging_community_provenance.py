"""Missing community research must not become an attributed community source."""

import pytest
from scripts.build_scentai_catalog_staging import wave_staging_row


def candidate():
    return {
        "product_id": "SOURCE-TEST-EDP-100",
        "brand": "Test",
        "name": "Source Test",
        "concentration": "Eau de Parfum",
        "volume_ml": 100,
    }


@pytest.mark.parametrize("community", [None, {}, {"source": None}, {"source": ""}])
def test_missing_source_stays_unknown(community):
    item = candidate()
    item["community"] = community
    row = wave_staging_row(item, wave_id="source-test", batch=99)
    assert row["community"]["source"] is None
    assert row["community"]["rating_10"] is None


def test_manufacturer_only_candidate_does_not_acquire_community_attribution():
    item = candidate()
    item["evidence"] = [{"url": "https://manufacturer.example/product"}]
    row = wave_staging_row(item, wave_id="source-test", batch=99)
    assert row["community"]["source"] is None
    assert row["research"]["evidence_urls"] == ["https://manufacturer.example/product"]


def test_explicit_community_evidence_is_preserved():
    item = candidate()
    item["community"] = {
        "source": "Parfumo",
        "rating_10": 8.1,
        "rating_count": 123,
        "longevity_10": 7.5,
        "projection_10": 7.0,
        "provisional": True,
    }
    row = wave_staging_row(item, wave_id="source-test", batch=99)
    assert row["community"] == item["community"]
