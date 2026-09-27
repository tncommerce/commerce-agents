"""Keep DUFYND CI on the supported Node 24 cache action runtime."""

from pathlib import Path

CI = Path(".github/workflows/ci.yml")

CACHE_V6_SHA = "55cc8345863c7cc4c66a329aec7e433d2d1c52a9"


def test_ci_uses_pinned_node24_cache_action() -> None:
    source = CI.read_text(encoding="utf-8")

    assert source.count(f"actions/cache@{CACHE_V6_SHA} # v6.1.0") == 2
    assert "actions/cache@0057852bfaa89a56745cba8c7296529d2fc39830 # v4" not in source
