# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

WORKFLOW = Path(".github/workflows/dufynd-production-smoke.yml")


def test_dufynd_production_smoke_covers_runtime_data_changes() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "branches: [scentai-mvp]" in workflow
    assert '- "examples/retail/api/**"' in workflow
    assert '- "examples/retail/data/**"' in workflow
    assert '- "examples/retail/storefront-web/**"' in workflow

def test_dufynd_production_smoke_requires_search_indexing_in_production() -> None:
    """Fail production smoke on accidental noindex; staging CLI stays flexible."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "branches: [scentai-mvp]" in workflow
    assert "if python scripts/dufynd_production_smoke.py --expected-indexing enabled; then" in workflow
    assert "if python scripts/dufynd_production_smoke.py; then" not in workflow
    # We do not change the observer read/ack/finalize or add a new schedule.

