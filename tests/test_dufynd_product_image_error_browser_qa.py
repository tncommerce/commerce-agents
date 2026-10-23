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
    # Real browsers can indefinitely wait on a licensed external photo without
    # firing onError. The visible original gets a bounded, scope-safe fallback.
    assert "PHOTO_LOAD_STALL_MS = 7_000" in visual
    assert "useEffect(() => {" in visual
    assert "IntersectionObserver" in visual
    assert 'rootMargin: "300px"' in visual
    assert "image.isConnected && (!image.complete || image.naturalWidth === 0)" in visual
    assert "primaryPhotoRef.current = image" in visual
    assert "imageUnavailable ? \"unavailable\" : \"missing\"" in visual


    image_qa = qa.split("const imageFailureContext", 1)[1]
    image_qa = image_qa.split("const merchantOfferTimeoutContext", 1)[0]
    assert 'route.abort("failed")' in image_qa
    assert "failPrimaryImage = false" in image_qa
    assert "const licensedUrl" in image_qa
    assert "media/catalog/product" in image_qa
    assert 'label: "product-image-error-fallback"' in image_qa
    assert 'label: "product-image-error-recovery"' in image_qa
    assert 'label: "product-image-stall-fallback"' in image_qa
    assert "blockedImageCount !== 1" in image_qa
    assert "stalled product photo did not become the neutral identity fallback" in image_qa
    assert 'label: "product-studio-background-source-isolation"' in image_qa
