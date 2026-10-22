"""A consented homepage page view must not depend on advisor session success."""

from pathlib import Path

PAGE = Path("examples/retail/storefront-web/app/page.tsx")
VISUAL_QA = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")
ANALYTICS = Path("examples/retail/storefront-web/lib/analytics.ts")


def test_home_pageview_does_not_wait_for_advisor_session() -> None:
    source = PAGE.read_text(encoding="utf-8")
    analytics = ANALYTICS.read_text(encoding="utf-8")
    effect = source.split("const trackCurrentPage = () => {", 1)[1]
    effect = effect.split("const unsubscribe =", 1)[0]

    assert "if (!measurementAllowed())" in effect
    assert "homepageViewTrackedRef.current = false" in effect
    assert "if (homepageViewTrackedRef.current) return" in effect
    assert "homepageViewTrackedRef.current = true" in effect
    assert 'trackAnalyticsEvent("page_view", { source: "storefront" })' in effect
    assert "session.sessionId" not in effect
    assert "subscribeMeasurement(trackCurrentPage)" in source
    assert "trackPageView={false}" in source  # No duplicate owner.
    assert 'trackAnalyticsEvent("consultation_start"' in source
    assert "export async function ensureAnalyticsSession" in analytics
    assert "const apiSessionId = await ensureAnalyticsSession()" in analytics


def test_actual_browser_qa_proves_advisor_independence() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")
    assert 'label: "home-pageview-advisor-independent"' in source
    assert "advisorSessionGate" in source
    assert 'new Error("advisor session request never began")' in source
    assert "advisorSessionStarted," in source
    assert "await advisorSessionStarted;" not in source
    assert 'await chooseMeasurement(homePageViewPage, "granted")' in source
    assert "firstPageViewObserved" in source
    assert "qa_home_pageview_independent" in source
    assert "pageViewEvents.length !== 1" in source
    assert 'pageViewEvents[0].acquisition_source !== "instagram"' in source


def test_broken_remote_image_wait_stays_bounded_and_fail_closed() -> None:
    """Allow neutral fallback to settle, never hide a persistent broken image."""
    source = VISUAL_QA.read_text(encoding="utf-8")
    assert "await sweepPage.waitForFunction(" in source
    assert "timeout: 2_500, polling: 100" in source
    assert 'image.naturalWidth === 0' in source
    assert 'if (diagnostics.visible_broken_images.length)' in source
    assert 'broken images: ${diagnostics.visible_broken_images.join(", ")}' in source
