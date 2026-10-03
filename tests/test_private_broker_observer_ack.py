from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from private_broker import observer_ack


class FakeResponse:
    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeClient:
    def __init__(self, *, posts: list[FakeResponse], token: str = "workload-token"):
        self.posts = list(posts)
        self.token = token
        self.post_calls: list[tuple[str, dict[str, Any]]] = []
        self.get_calls: list[tuple[str, dict[str, Any]]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str, **kwargs):
        self.get_calls.append((url, kwargs))
        return FakeResponse(200, {"value": self.token})

    def post(self, url: str, **kwargs):
        self.post_calls.append((url, kwargs))
        return self.posts.pop(0)


def write_plan(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "acks": [
                    {"thread_id": thread_id, "observation_id": f"{index:x}" * 64}
                    for index, thread_id in enumerate(observer_ack.THREADS, start=1)
                ],
            }
        ),
        encoding="utf-8",
    )


def configure_oidc(monkeypatch) -> None:
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://oidc.example/token")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "request-token")


def test_acknowledges_fixed_plan_then_verifies_idempotency(monkeypatch, tmp_path: Path) -> None:
    configure_oidc(monkeypatch)
    plan = tmp_path / "broker-acks.json"
    write_plan(plan)
    client = FakeClient(
        posts=[
            *[FakeResponse(200, {"status": "acknowledged"}) for _ in observer_ack.THREADS],
            *[FakeResponse(200, {"status": "duplicate"}) for _ in observer_ack.THREADS],
        ]
    )

    summary = observer_ack.acknowledge(
        "https://broker.example",
        plan,
        client_factory=lambda **kwargs: client,
    )

    assert summary == {
        "acknowledged": 3,
        "duplicate_first_pass": 0,
        "idempotent_rechecks": 3,
    }
    assert len(client.get_calls) == 1
    assert len(client.post_calls) == 6
    for index, (thread_id, digest) in enumerate(observer_ack.load_ack_plan(plan)):
        first_url, first_kwargs = client.post_calls[index]
        second_url, second_kwargs = client.post_calls[index + 3]
        expected = f"https://broker.example/v1/gmail/threads/{thread_id}/ack/{digest}"
        assert first_url == expected
        assert second_url == expected
        assert first_kwargs["headers"]["Authorization"] == "Bearer workload-token"
        assert second_kwargs["headers"]["Authorization"] == "Bearer workload-token"


def test_ack_recovery_accepts_first_pass_duplicates(monkeypatch, tmp_path: Path) -> None:
    configure_oidc(monkeypatch)
    plan = tmp_path / "broker-acks.json"
    write_plan(plan)
    client = FakeClient(
        posts=[
            FakeResponse(200, {"status": "duplicate"}),
            FakeResponse(200, {"status": "acknowledged"}),
            FakeResponse(200, {"status": "duplicate"}),
            *[FakeResponse(200, {"status": "duplicate"}) for _ in observer_ack.THREADS],
        ]
    )

    summary = observer_ack.acknowledge(
        "https://broker.example",
        plan,
        client_factory=lambda **kwargs: client,
    )

    assert summary["acknowledged"] == 1
    assert summary["duplicate_first_pass"] == 2
    assert summary["idempotent_rechecks"] == 3


def test_rejects_unknown_or_duplicate_thread_before_oidc(monkeypatch, tmp_path: Path) -> None:
    configure_oidc(monkeypatch)
    plan = tmp_path / "broker-acks.json"
    write_plan(plan)
    payload = json.loads(plan.read_text(encoding="utf-8"))
    payload["acks"][2]["thread_id"] = payload["acks"][0]["thread_id"]
    plan.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(observer_ack.AckFailure, match="ack_value_mismatch"):
        observer_ack.acknowledge(
            "https://broker.example",
            plan,
            client_factory=lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("network must not be reached")
            ),
        )


def test_http_failure_exposes_only_bounded_status(monkeypatch, tmp_path: Path) -> None:
    configure_oidc(monkeypatch)
    plan = tmp_path / "broker-acks.json"
    write_plan(plan)
    client = FakeClient(posts=[FakeResponse(403, {"error": "secret-provider-detail"})])

    with pytest.raises(observer_ack.AckFailure) as exc:
        observer_ack.acknowledge(
            "https://broker.example",
            plan,
            client_factory=lambda **kwargs: client,
        )

    message = str(exc.value)
    assert message == f"ack:{observer_ack.THREADS[0]}:http_403"
    assert "secret-provider-detail" not in message
    assert "workload-token" not in message
    assert "request-token" not in message


def test_rejects_non_idempotent_second_pass(monkeypatch, tmp_path: Path) -> None:
    configure_oidc(monkeypatch)
    plan = tmp_path / "broker-acks.json"
    write_plan(plan)
    client = FakeClient(
        posts=[
            *[FakeResponse(200, {"status": "acknowledged"}) for _ in observer_ack.THREADS],
            FakeResponse(200, {"status": "acknowledged"}),
        ]
    )

    with pytest.raises(observer_ack.AckFailure, match="not_idempotent"):
        observer_ack.acknowledge(
            "https://broker.example",
            plan,
            client_factory=lambda **kwargs: client,
        )
