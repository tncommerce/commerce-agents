"""Conversion QA must wait for hydrated React search handlers before input."""

from pathlib import Path

QA = Path("examples/retail/storefront-web/scripts/conversion-search-qa.mjs")


def test_social_search_waits_for_real_react_event_handlers() -> None:
    source = QA.read_text(encoding="utf-8")
    start = source.split("const input=page.getByLabel('Duft oder Marke suchen'", 1)[1]
    start = start.split("const guide=page.locator", 1)[0]
    assert "start?qa=1&src=instagram&cmp=qa_conversion&content=qa_search" in source
    assert "waitUntil:'load'" in source
    assert "input.waitFor({state:'visible'})" in start
    assert "page.waitForFunction(" in start
    assert "key.startsWith('__reactProps$')" in start
    assert "timeout:12_000" in start
    assert start.index("key.startsWith('__reactProps$')") < start.index(
        "await input.fill('Libre YSL EDP 90ml')"
    )
    assert "getByRole('link').first().waitFor({state:'visible',timeout:12_000})" in start
    assert "verifyProductNameAliases(browser, baseUrl, outputDir)" in source
    assert "Conversion QA must never trigger a clickout" in source
