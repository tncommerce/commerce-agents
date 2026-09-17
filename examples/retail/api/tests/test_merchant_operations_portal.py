from demo_common.tests.fixtures import (
    start_operator,
)


FLEET_STATUS_PATH = (
    "/api/merchant/operations/fleet-status"
)


def test_fleet_status_route_requires_merchant_session(
    client,
) -> None:
    response = client.get(
        FLEET_STATUS_PATH
    )

    assert response.status_code == 401


def test_fleet_status_route_returns_consistent_summary(
    client,
) -> None:
    headers = start_operator(client)

    response = client.get(
        FLEET_STATUS_PATH,
        headers=headers,
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["total_jobs"] == len(
        payload["jobs"]
    )

    assert payload["attention_required"] == len(
        payload["attention_items"]
    )

    health_total = (
        payload["health_ok"]
        + payload["health_info"]
        + payload["health_warning"]
        + payload["health_blocked"]
    )

    assert health_total == payload["total_jobs"]
