"""Keep the DUFYND storefront environment template aligned with launch gates."""

from __future__ import annotations

import re
from pathlib import Path

ENV_TEMPLATE = Path("examples/retail/storefront-web/.env.example")
LAUNCH_CHECK = Path("examples/retail/storefront-web/scripts/check-launch-readiness.mjs")

REQUIRED_PUBLIC_ENV = {
    "NEXT_PUBLIC_API_URL",
    "NEXT_PUBLIC_SITE_URL",
    "NEXT_PUBLIC_SITE_INDEXABLE",
    "NEXT_PUBLIC_LEGAL_BUSINESS_NAME",
    "NEXT_PUBLIC_LEGAL_OWNER_NAME",
    "NEXT_PUBLIC_LEGAL_STREET",
    "NEXT_PUBLIC_LEGAL_POSTCODE",
    "NEXT_PUBLIC_LEGAL_CITY",
    "NEXT_PUBLIC_LEGAL_EMAIL",
}


def template_keys() -> set[str]:
    source = ENV_TEMPLATE.read_text(encoding="utf-8")
    return {
        match.group(1)
        for match in re.finditer(
            r"^(NEXT_PUBLIC_[A-Z0-9_]+)=",
            source,
            re.MULTILINE,
        )
    }


def test_storefront_env_template_covers_launch_required_public_values() -> None:
    keys = template_keys()
    assert REQUIRED_PUBLIC_ENV.issubset(keys)


def test_launch_checker_and_env_template_reference_same_required_values() -> None:
    checker = LAUNCH_CHECK.read_text(encoding="utf-8")
    keys = template_keys()

    for key in REQUIRED_PUBLIC_ENV:
        assert key in checker
        assert key in keys


def test_indexing_template_stays_fail_closed() -> None:
    source = ENV_TEMPLATE.read_text(encoding="utf-8")
    assert "NEXT_PUBLIC_SITE_INDEXABLE=false" in source
    assert "NEXT_PUBLIC_SITE_INDEXABLE=true" not in source
