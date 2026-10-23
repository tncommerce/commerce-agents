from pathlib import Path

QA_SCRIPT = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")


def test_visual_qa_bounds_remote_image_decode_waits() -> None:
    text = QA_SCRIPT.read_text(encoding="utf-8")

    assert "const imageDecodeTimeoutMs = 8_000;" in text
    assert "Promise.race([" in text
    assert "window.setTimeout(resolve, decodeTimeoutMs)" in text
    assert ".filter((image) => image.isConnected && !image.complete)" in text
    assert "await sweepPage.evaluate(async (decodeTimeoutMs)" in text
    assert "visible_pending_images: visiblePendingImages" in text
    assert "if (diagnostics.visible_pending_images.length)" in text
    assert "if (diagnostics.visible_broken_images.length)" in text
    assert "images did not settle within" in text
