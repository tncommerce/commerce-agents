"""Opt-in deterministic pricing time for mocked provider unit tests."""

import json
from datetime import datetime, timedelta

import pytest


@pytest.fixture
def counted_contract_clock(monkeypatch):
    from scripts import dufynd_anthropic_counted as counted

    contract = json.loads(counted.PRICING.read_bytes())
    verified = datetime.fromisoformat(contract["verified_at"])
    original = counted.pricing

    def fixture_pricing(now=None):
        # Only the implicit unit-test clock is pinned. Explicit expiry checks
        # still run the real guard, and production pricing is unchanged.
        return original(now if now is not None else verified + timedelta(seconds=1))

    monkeypatch.setattr(counted, "pricing", fixture_pricing)
