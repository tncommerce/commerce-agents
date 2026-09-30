from pathlib import Path

VISUAL = Path("examples/retail/storefront-web/components/FragranceVisual.tsx")
QA = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")


def test_image_error_fallback_preserves_identity_and_browser_recovery_coverage() -> None:
    visual = VISUAL.read_text(encoding="utf-8")
    qa = QA.read_text(encoding="utf-8")

    assert 'imageUnavailable ? "unavailable" : "missing"' in visual
    assert "Produktbild derzeit nicht verfügbar" in visual
    assert "Kein freigegebenes Produktbild" in visual
    assert "failedImageUrl === resolvedImageUrl" in visual
    assert "image?.complete && image.naturalWidth === 0" in visual
    assert "onError={() => setFailedImageUrl(resolvedImageUrl)}" in visual
    assert "failedBackdropUrl !== backdropUrl" in visual
    assert "onError={() => setFailedBackdropUrl(backdropUrl)}" in visual

    image_qa = qa.split("const imageFailureContext", 1)[1]
    image_qa = image_qa.split("const merchantOfferTimeoutContext", 1)[0]
    assert 'route.abort("failed")' in image_qa
    assert "failPrimaryImage = false" in image_qa
    assert "failBackdropImage = true" in image_qa
    assert 'label: "product-image-error-fallback"' in image_qa
    assert 'label: "product-image-error-recovery"' in image_qa
    assert 'label: "decorative-image-error-isolation"' in image_qa
