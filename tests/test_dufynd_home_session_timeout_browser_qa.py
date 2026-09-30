from pathlib import Path

PAGE = Path("examples/retail/storefront-web/app/page.tsx")
SESSION = Path("examples/web-shared/session.ts")
API = Path("examples/web-shared/api.ts")
QA = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")


def test_homepage_session_timeout_is_opt_in_and_mobile_recovery_is_covered() -> None:
    page = PAGE.read_text(encoding="utf-8")
    session = SESSION.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    qa = QA.read_text(encoding="utf-8")

    assert "useSession(api, { timeoutMs: 8_000 })" in page
    assert "timeoutMs?: number" in session
    assert "timeoutMs !== undefined && Number.isFinite(timeoutMs) && timeoutMs > 0" in session
    assert "controller?.signal" in session
    assert "setTimeout(() => controller.abort(), timeoutMs)" in session
    assert "clearTimeout(timeoutId)" in session
    assert "controller?.abort()" in session
    assert "settled: true" in session
    assert "if (!current()) return" in session
    assert "signal?: AbortSignal" in api
    assert '"/session", body, signal' in api

    home_qa = qa.split("const homeSessionTimeoutContext", 1)[1]
    home_qa = home_qa.split("const productDetailAttributionContext", 1)[0]
    assert "setTimeout(resolve, 8_500)" in home_qa
    assert 'failOpenUrl.searchParams.has("sid")' in home_qa
    assert "homeSessionRecoveryAllowed = true" in home_qa
    assert 'recoveredUrl.searchParams.get("sid") !== recoveredHomeSessionId' in home_qa
    assert 'label: "storefront-session-request-timeout"' in home_qa
    assert 'label: "storefront-session-timeout-recovery"' in home_qa
