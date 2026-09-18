from __future__ import annotations

from retail.api.main import health


async def test_scentai_health_endpoint_payload() -> None:
    payload = await health()

    assert payload == {
        "ok": True,
        "service": "scentai-api",
    }
