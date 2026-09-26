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


def test_launch_readiness_rejects_placeholder_public_urls() -> None:
    readiness_source = READINESS.read_text(encoding="utf-8")

    assert "RESERVED_LAUNCH_HOSTS" in readiness_source
    for reserved_host in ("example.com", "example.org", "example.net", "localhost"):
        assert f'"{reserved_host}"' in readiness_source

    assert "validPublicHttpUrl(apiUrl)" in readiness_source
    assert "validPublicHttpUrl(siteUrl)" in readiness_source
    assert "non-placeholder HTTPS public API URL" in readiness_source


def test_launch_readiness_tolerates_only_small_future_clock_skew() -> None:
    readiness_source = READINESS.read_text(encoding="utf-8")

    assert "MAX_FUTURE_CLOCK_SKEW_HOURS = 5 / 60" in readiness_source
    assert "ageHours >= -MAX_FUTURE_CLOCK_SKEW_HOURS" in readiness_source
    assert "ageHours <= 72" in readiness_source
