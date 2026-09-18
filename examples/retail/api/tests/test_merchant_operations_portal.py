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


JOB_STATUS_PATH = (
    "/api/merchant/operations/jobs/notino-de"
)


def test_job_status_route_requires_merchant_session(
    client,
) -> None:
    response = client.get(
        JOB_STATUS_PATH
    )

    assert response.status_code == 401


def test_job_status_route_returns_notino_detail(
    client,
) -> None:
    headers = start_operator(client)

    response = client.get(
        JOB_STATUS_PATH,
        headers=headers,
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"]["job_id"] == "notino-de"
    assert payload["status"]["job_state"] == "disabled"

    assert payload["health"]["job_id"] == "notino-de"
    assert payload["health"]["severity"] == "info"

    assert payload["attention"] is None


def test_unknown_job_status_route_is_not_registered(
    client,
) -> None:
    headers = start_operator(client)

    response = client.get(
        "/api/merchant/operations/jobs/unknown-job",
        headers=headers,
    )

    assert response.status_code == 404
