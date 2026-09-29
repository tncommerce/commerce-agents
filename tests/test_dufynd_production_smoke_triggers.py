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
