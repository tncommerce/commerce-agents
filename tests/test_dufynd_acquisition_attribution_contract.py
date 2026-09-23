from __future__ import annotations

from pathlib import Path


ACQUISITION_COMPONENT = Path(
    "examples/retail/storefront-web/components/AcquisitionAnalytics.tsx"
)
ANALYTICS_LIBRARY = Path(
    "examples/retail/storefront-web/lib/analytics.ts"
)


def test_launch_query_parameter_contract_stays_stable() -> None:
    component = ACQUISITION_COMPONENT.read_text(encoding="utf-8-sig")

    assert 'params.get("src")' in component
    assert 'params.get("cmp")' in component
    assert 'params.get("content")' in component
    assert "source: explicitChannel" in component
    assert "campaignId" in component
    assert "contentId" in component


def test_launch_attribution_is_persisted_into_analytics_payload() -> None:
    analytics = ANALYTICS_LIBRARY.read_text(encoding="utf-8-sig")

    assert 'const ACQUISITION_STORAGE_KEY = "dufynd_acquisition_attribution_v1"' in analytics
    assert "acquisition_source: attribution?.source" in analytics
    assert "campaign_id: attribution?.campaign_id" in analytics
    assert "content_id: attribution?.content_id" in analytics


def test_launch_attribution_is_forwarded_to_internal_urls() -> None:
    analytics = ANALYTICS_LIBRARY.read_text(encoding="utf-8-sig")

    assert 'target.searchParams.set("src", attribution.source)' in analytics
    assert 'target.searchParams.set(' in analytics
    assert '"cmp",' in analytics
    assert '"content",' in analytics
