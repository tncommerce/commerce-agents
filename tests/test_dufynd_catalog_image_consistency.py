"""Presentation guards; these do not substitute for live visual browser QA."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "examples/retail/storefront-web/components"


def source() -> str:
    return (COMPONENTS / "FragranceVisual.tsx").read_text()


def stylesheet() -> str:
    return (COMPONENTS / "FragranceVisual.module.css").read_text()


def test_catalog_uses_one_surface_while_hero_keeps_world():
    assert 'variant === "card" ? "#f5f3ee" : WORLD_BACKGROUNDS[world]' in source()
    assert 'variant === "card" ? styles.catalog : ""' in source()


def test_same_card_treatment_covers_three_source_states():
    code = source()
    assert code.count("${catalogClass}") == 3
    assert 'data-dufynd-image-kind="editorial"' in code
    assert 'data-dufynd-image-kind="missing"' in code
    assert 'data-dufynd-image-kind={cutoutUrl ? "cutout" : "photograph"}' in code


def test_frozen_image_sources_and_fallbacks_are_preserved():
    code = source()
    assert "const resolvedImageUrl = cutoutUrl || imageUrl;" in code
    assert "src={resolvedImageUrl}" in code
    assert "src={imageUrl}" in code
    assert "setFailedImageUrl(resolvedImageUrl)" in code
    assert "Kein freigegebenes Produktbild" in code
    assert "Produktbild derzeit nicht verfügbar" in code


def test_catalog_does_not_load_decorative_duplicate_backdrops():
    code = source()
    assert '{variant === "hero" && imageUrl ? (' in code
    assert 'variant === "hero" && backdropUrl && failedBackdropUrl !== backdropUrl' in code


def test_pointer_depth_is_hero_only_and_reduced_motion_guard_remains():
    code = source()
    assert code.count('onPointerMove={variant === "hero" ? updatePointer : undefined}') == 2
    assert code.count('onPointerLeave={variant === "hero" ? resetPointer : undefined}') == 2
    assert "(prefers-reduced-motion: reduce)" in code
    assert 'event.pointerType === "touch"' in code


def test_editorial_images_are_not_presented_as_verified_packshots():
    code = source()
    assert "stilisierte DUFYND-Inszenierung" in code
    assert "<span className={styles.editorialLabel}>Inszenierung</span>" in code


def test_card_containment_does_not_crop_or_recolour_bottles():
    css = stylesheet()
    assert "object-fit: contain;" in css
    assert "object-fit: cover" not in css
    assert "inset: 10% 12% 12%;" in css
    assert "saturate(" not in css
    assert "mix-blend-mode" not in css
    assert "hue-rotate(" not in css
    assert "url(" not in css


def test_card_shadows_are_cutout_specific_and_no_infinite_animation():
    css = stylesheet()
    assert '[data-dufynd-image-kind="cutout"]' in css
    assert "filter: none;" in css
    assert "drop-shadow(0 9px 10px" in css
    assert "@keyframes" not in css
    assert "!important" not in css


def test_original_loading_alt_and_priority_contracts_survive():
    code = source()
    assert "alt={displayAlt}" in code
    assert 'loading={priority ? "eager" : "lazy"}' in code
    assert 'fetchPriority={priority ? "high" : "auto"}' in code
    assert 'decoding="async"' in code
