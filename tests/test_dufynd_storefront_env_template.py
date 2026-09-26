"""Keep the DUFYND storefront launch environment template complete."""

from __future__ import annotations

import re
from pathlib import Path

READINESS = Path("examples/retail/storefront-web/scripts/check-launch-readiness.mjs")
TEMPLATE = Path("examples/retail/storefront-web/.env.example")

ENV_PATTERN = re.compile(r'env\("(?P<name>NEXT_PUBLIC_[A-Z0-9_]+)"\)')


def test_storefront_env_template_covers_launch_readiness_variables() -> None:
    readiness_source = READINESS.read_text(encoding="utf-8")
    required = set(ENV_PATTERN.findall(readiness_source))

    template_lines = TEMPLATE.read_text(encoding="utf-8").splitlines()
    documented = {
        line.split("=", 1)[0].strip()
        for line in template_lines
        if line.strip().startswith("NEXT_PUBLIC_") and "=" in line
    }

    assert required
    assert required <= documented


def test_storefront_env_template_keeps_search_indexing_opt_in() -> None:
    template = TEMPLATE.read_text(encoding="utf-8")
    assert "NEXT_PUBLIC_SITE_INDEXABLE=false" in template
    assert "NEXT_PUBLIC_SITE_URL=https://dufynd.de" in template
