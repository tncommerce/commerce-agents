"""Keep DUFYND fragrance detail pages easy to share without backend state."""

from pathlib import Path

DETAIL_PAGE = Path("examples/retail/storefront-web/app/duft/[slug]/page.tsx")
SHARE_BUTTON = Path("examples/retail/storefront-web/components/FragranceShareButton.tsx")


def test_fragrance_detail_exposes_share_action() -> None:
    page = DETAIL_PAGE.read_text(encoding="utf-8")

    assert 'import FragranceShareButton from "@/components/FragranceShareButton"' in page
    assert "<FragranceShareButton" in page
    assert "brand={fragrance.brand}" in page
    assert "name={fragrance.name}" in page


def test_share_control_prefers_native_share_and_falls_back_to_clipboard() -> None:
    source = SHARE_BUTTON.read_text(encoding="utf-8")

    assert 'typeof navigator.share === "function"' in source
    assert "await navigator.share({" in source
    assert "navigator.clipboard?.writeText" in source
    assert "await navigator.clipboard.writeText(url)" in source
    assert 'error.name === "AbortError"' in source
    assert 'role="status"' in source
    assert 'aria-live="polite"' in source
