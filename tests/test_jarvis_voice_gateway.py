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


def test_voice_gateway_session_is_read_only_tool_enabled_and_conversational():
    gateway = JarvisVoiceGateway(owner_id=str(uuid4()), api_key="sk-test")
    config = gateway.session_config()
    assert config["type"] == "realtime"
    assert config["model"] == DEFAULT_MODEL
    assert config["output_modalities"] == ["audio"]
    assert config["max_output_tokens"] == 4096
    assert config["tool_choice"] == "auto"
    assert len(config["tools"]) == 2
    tool = config["tools"][0]
    assert tool["type"] == "function"
    assert tool["name"] == "inspect_dufynd"
    assert "Read-only" in tool["description"]
    assert tool["parameters"]["required"] == ["area"]
    assert tool["parameters"]["additionalProperties"] is False
    assert "workers" in tool["parameters"]["properties"]["area"]["enum"]
    assert "first_money" in tool["parameters"]["properties"]["area"]["enum"]

    action_tool = config["tools"][1]
    assert action_tool["type"] == "function"
    assert action_tool["name"] == "advance_dufynd_safe_work"
    assert "protected zero-spend worker" in action_tool["description"]
    assert action_tool["parameters"]["properties"] == {}
    assert action_tool["parameters"]["additionalProperties"] is False

    turn = config["audio"]["input"]["turn_detection"]
    assert turn["type"] == "semantic_vad"
    assert turn["eagerness"] == "high"
    assert turn["create_response"] is True
    assert turn["interrupt_response"] is False

    assert config["audio"]["output"]["voice"] == "ash"
    assert config["audio"]["output"]["speed"] == 1.03
    assert "operative CEO-Assistent von Master" in config["instructions"]
    assert "immer als 'Master'" in config["instructions"]
    assert "MUSST du zuerst inspect_dufynd" in config["instructions"]
    assert "operator_diagnosis" in config["instructions"]
    assert "publication_truth" in config["instructions"]
    assert "stopped_before_publish" in config["instructions"]
    assert "niemals automatisch der globale Grund" in config["instructions"]
    assert "Sag Master niemals, er solle E-Mails prüfen" in config["instructions"]
    assert "niemals 'wahrscheinlich'" in config["instructions"]
    assert "nicht verifiziert" in config["instructions"]
    assert "Übersetze interne Implementierungsbegriffe" in config["instructions"]
    assert "zwei bis vier konkrete, priorisierte Lösungsvorschläge" in config["instructions"]
    assert "advance_dufynd_safe_work" in config["instructions"]
    assert "trockener, intelligenter Humor" in config["instructions"]
    assert "britisch/RP-geprägte Sprechmelodie" in config["instructions"]
    assert "Beende begonnene Sätze" in config["instructions"]
    assert "Tuan" not in config["instructions"]


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
    assert b"4096" in seen["body"]
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
