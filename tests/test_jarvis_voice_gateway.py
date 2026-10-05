from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from retail.api.jarvis_voice import (
    DEFAULT_MODEL,
    JarvisVoiceGateway,
    VoiceUnavailable,
)


def test_voice_gateway_session_is_manual_tool_free_and_bounded():
    gateway = JarvisVoiceGateway(owner_id=str(uuid4()), api_key="sk-test")
    config = gateway.session_config()
    assert config["type"] == "realtime"
    assert config["model"] == DEFAULT_MODEL
    assert config["output_modalities"] == ["audio"]
    assert config["max_output_tokens"] == 256
    assert config["tools"] == []
    assert config["audio"]["input"]["turn_detection"] is None
    assert config["audio"]["output"]["voice"] == "echo"
    assert config["audio"]["output"]["speed"] == 0.92
    assert "keine externen" in config["instructions"]
    assert "Owner-Gates" in config["instructions"]
    assert "britischer Prosodie" in config["instructions"]
    assert "ohne eine reale Person" in config["instructions"]


def test_voice_gateway_keeps_standard_key_server_side_and_returns_only_sdp():
    owner_id = str(uuid4())
    seen = {}

    def transport(request):
        seen["authorization"] = request.headers.get("authorization")
        seen["safety"] = request.headers.get("openai-safety-identifier")
        seen["content_type"] = request.headers.get("content-type")
        seen["body"] = request.content
        return httpx.Response(
            201,
            text="v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\n",
            headers={"content-type": "application/sdp"},
        )

    gateway = JarvisVoiceGateway(
        owner_id=owner_id,
        api_key="sk-server-only-test",
        transport=httpx.MockTransport(transport),
    )
    answer = gateway.connect("v=0\r\no=- 2 2 IN IP4 127.0.0.1\r\n")
    assert answer.startswith("v=0")
    assert seen["authorization"] == "Bearer sk-server-only-test"
    assert len(seen["safety"]) == 64
    assert seen["safety"] != owner_id
    assert seen["content_type"].startswith("multipart/form-data;")
    assert b"gpt-realtime-2.1-mini" in seen["body"]
    assert b"sk-server-only-test" not in seen["body"]


def test_voice_gateway_fails_closed_without_provider_key():
    gateway = JarvisVoiceGateway(owner_id=str(uuid4()), api_key="")
    assert gateway.enabled is False
    with pytest.raises(VoiceUnavailable):
        gateway.connect("v=0\r\n")


def test_voice_gateway_rejects_invalid_sdp_before_provider_call():
    gateway = JarvisVoiceGateway(owner_id=str(uuid4()), api_key="sk-test")
    with pytest.raises(ValueError, match="invalid_sdp"):
        gateway.connect("not-sdp")


def test_voice_gateway_bounds_session_creation_rate():
    gateway = JarvisVoiceGateway(owner_id=str(uuid4()), api_key="sk-test")
    for _ in range(8):
        gateway.check_attempt()
    with pytest.raises(HTTPException) as exc:
        gateway.check_attempt()
    assert exc.value.status_code == 429
