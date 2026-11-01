"""The example's font loader must not make all DUFYND CI depend on Google."""

from pathlib import Path

APP = Path("examples/entertainment/storefront-web/app")


def test_acme_sample_has_no_external_font_build_dependency() -> None:
    layout = (APP / "layout.tsx").read_text(encoding="utf-8")
    css = (APP / "globals.css").read_text(encoding="utf-8")
    assert 'from "next/font/google"' not in layout
    assert 'from "next/font/local"' not in layout
    assert 'className="at-fonts-local"' in layout
    for variable in ("--font-display:", "--font-body:", "--font-mono:"):
        assert variable in css
    assert "fonts.googleapis.com" not in layout + css
    assert "fonts.gstatic.com" not in layout + css
    assert "url(http" not in layout + css
