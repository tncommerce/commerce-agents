"""Keep the DUFYND public composer screen-reader label localized."""

from pathlib import Path

SHELL = Path("examples/web-shared/storefront/Shell.tsx")
PAGE = Path("examples/retail/storefront-web/app/page.tsx")


def test_store_shell_supports_optional_localized_composer_label() -> None:
    source = SHELL.read_text(encoding="utf-8")

    assert "composerLabel?: string;" in source
    assert "label={composerLabel ?? `Message ${assistantName}`}" in source


def test_dufynd_sets_german_composer_accessibility_label() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert 'composerLabel="Nachricht an DUFYND Advisor"' in source
