"""Static safety contract for the zero-cost Jarvis Live Interface V1."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROOM = ROOT / "examples" / "retail" / "api" / "control_room"


def test_ptt_control_is_explicit_and_local_only():
    html = (ROOM / "index.html").read_text(encoding="utf-8")
    assert 'id="jarvis-ptt"' in html
    assert 'aria-pressed="false"' in html
    assert "Button oder V halten" in html
    assert "keine" in html and "Audio-Übertragung" in html


def test_phase1_microphone_reactor_has_no_realtime_transport():
    js = (ROOM / "room.js").read_text(encoding="utf-8")
    start = js.index("// JARVIS LIVE INTERFACE V1")
    end = js.index("  function missions()", start)
    voice = js[start:end]

    assert "navigator.mediaDevices.getUserMedia" in voice
    assert "echoCancellation: true" in voice
    assert "noiseSuppression: true" in voice
    assert "dufynd:jarvis-ptt-start" in voice
    assert "dufynd:jarvis-ptt-stop" in voice
    assert "window.DUFYNDJarvisVoice" in voice
    assert "getTracks().forEach((track) => track.stop())" in voice
    assert "context.close()" in voice

    # Phase 1 is visualization only. Voice transport/API wiring is a separate,
    # explicitly approved phase so holding PTT cannot create provider spend.
    assert "RTCPeerConnection" not in voice
    assert "WebSocket" not in voice
    assert "/realtime" not in voice
    assert "api.openai.com" not in voice


def test_voice_animation_respects_reduced_motion():
    css = (ROOM / "room.css").read_text(encoding="utf-8")
    assert "JARVIS LIVE INTERFACE V1" in css
    assert '.core[data-voice-state="listening"]' in css
    assert ".core-spectrum" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
