from pathlib import Path

API = Path("examples/retail/storefront-web/lib/api.ts")
ANALYTICS = Path("examples/retail/storefront-web/lib/analytics.ts")
QA = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")


def test_analytics_owned_session_has_bounded_wait_and_recovery_coverage() -> None:
    api_source = API.read_text(encoding="utf-8")
    request = api_source.split("export async function initializeAnalyticsSession", 1)[1]
    request = request.split("export async function fetchProducts", 1)[0]
    analytics_source = ANALYTICS.read_text(encoding="utf-8")
    qa_source = QA.read_text(encoding="utf-8")

    assert "const ANALYTICS_SESSION_TIMEOUT_MS = 8_000;" in api_source
    assert "controller.abort()" in request
    assert "signal: controller.signal" in request
    assert "headers: api.headers()" in request
    assert 'method: "POST"' in request
    assert "clearTimeout(timeoutId)" in request
    initializer = analytics_source.split("export async function ensureAnalyticsSession", 1)[1]
    initializer = initializer.split("export type AnalyticsEventName", 1)[0]
    assert "if (!measurementAllowed()) return null;" in initializer
    assert "const pending = initializeAnalyticsSession().then(" in initializer
    assert "if (!measurementStillAllowed(epoch)) return null;" in initializer
    assert "if (apiSessionPromise === pending) apiSessionPromise = null;" in initializer
    assert "apiSessionPromise = pending;" in initializer

    timeout_qa = qa_source.split("const analyticsSessionTimeoutContext", 1)[1]
    timeout_qa = timeout_qa.split("const attributionClickoutContext", 1)[0]
    assert "setTimeout(resolve, 8_500)" in timeout_qa
    assert 'const measurementSid = failOpenUrl.searchParams.get("sid")' in timeout_qa
    assert 'measurementSid === recoveredSessionId' in timeout_qa
    assert 'failOpenUrl.searchParams.get("measurement") !== "granted-v1"' in timeout_qa
    assert "sessionRecoveryAllowed = true" in timeout_qa
    assert 'recoveredUrl.searchParams.get("sid") !== measurementSid' in timeout_qa
    assert 'recoveredUrl.searchParams.get("measurement") !== "granted-v1"' in timeout_qa
    assert 'label: "analytics-session-request-timeout"' in timeout_qa
    assert 'label: "analytics-session-timeout-recovery"' in timeout_qa
