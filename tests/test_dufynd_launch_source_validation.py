"""Keep strict launch readiness blocked by unresolved live source validation."""

from pathlib import Path

READINESS = Path("examples/retail/storefront-web/scripts/check-launch-readiness.mjs")


def test_launch_checker_consumes_live_source_validation_blockers() -> None:
    source = READINESS.read_text(encoding="utf-8")

    assert "const liveSourceValidationBlockers = liveProducts.flatMap" in source
    assert "sourceProduct?.validation?.blockers" in source
    assert '"live_source_validation"' in source
    assert 'liveSourceValidationBlockers.length ? "gate" : "pass"' in source
