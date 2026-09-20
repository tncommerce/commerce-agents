from __future__ import annotations

from fastapi.testclient import TestClient

from retail.api import main


def test_dufynd_health_endpoint_payload() -> None:
    client = TestClient(
        main.app,
        base_url="http://localhost",
        client=("127.0.0.1", 12345),
    )

    payload = client.get("/api/health").json()

    assert payload["ok"] is True
    assert payload["store"] == "DUFYND"
    assert payload["products"] == len(main.backend.products)
    assert payload["skills"] == main.agent.skills.names
    assert payload["model"] == main.agent.config.model
