"""Static safety contract for DUFYND Jarvis Live Interface V2."""


def room_text(filename):
    with open(
        "examples/retail/api/control_room/" + filename,
        encoding="utf-8",
    ) as handle:
        return handle.read()


def test_ptt_control_is_explicit_and_bounded():
    html = room_text("index.html")
    assert 'id="jarvis-ptt"' in html
    assert 'aria-pressed="false"' in html
    assert "Button oder V halten" in html
    assert "PHASE 2" in html
    assert "Audio nur während gedrückter Taste" in html


def test_phase2_uses_same_origin_webrtc_bridge_and_manual_turn_control():
    js = room_text("room.js")
    start = js.index("// JARVIS LIVE INTERFACE V2")
    end = js.index("  function missions()", start)
    voice = js[start:end]

    assert "navigator.mediaDevices.getUserMedia" in voice
    assert "new RTCPeerConnection()" in voice
    assert 'createDataChannel("oai-events")' in voice
    assert 'fetch("/internal/jarvis/voice/session"' in voice
    assert '"Content-Type": "application/sdp"' in voice
    assert '"X-CSRF-Token": csrf' in voice
    assert 'stage.dataset.voiceEnabled === "true"' in voice
    assert '"VOICE NICHT AKTIV"' in voice
    assert 'type: "input_audio_buffer.clear"' in voice
    assert 'type: "input_audio_buffer.commit"' in voice
    assert 'type: "response.create"' in voice
    assert "track.enabled = false" in voice
    assert "setTimeout(() => stop(), 20000)" in voice
    assert "30000" in voice
    assert "startOutputAnalysis(event.streams[0])" in voice
    assert "drawOutputSpectrum" in voice
    assert "waitForIce" not in voice
    assert "peer.localDescription?.sdp || offer.sdp" in voice
    assert '"HÖRT ZU · jetzt sprechen · Loslassen sendet deine Frage"' in voice
    assert '"NOCH NICHT BEREIT"' in voice
    assert '"MIKROFON BLOCKIERT"' in voice
    assert '"REALTIME TIMEOUT"' in voice
    assert "button.dataset.providerReady" in voice
    assert '"VOICE NICHT AKTIV"' in voice
    assert '"Server-Key fehlt · Push-to-Talk kann noch nicht antworten"' in voice
    assert "api.openai.com" not in voice
    assert "OPENAI_API_KEY" not in voice


def test_voice_context_is_bounded_and_action_free():
    js = room_text("room.js")
    start = js.index("// JARVIS LIVE INTERFACE V2")
    end = js.index("  function missions()", start)
    voice = js[start:end]

    assert "DUFYND-LIVE-STATUS" in voice
    assert "safeCode" in voice
    assert "safeSha" in voice
    assert "safeCount" in voice
    assert ".slice(0, 8)" in voice
    assert "worker.task_id" in voice
    assert "conversation.item.create" in voice


def test_voice_animation_respects_reduced_motion():
    css = room_text("room.css")
    assert "JARVIS LIVE INTERFACE V2" in css
    assert '.core[data-voice-state="listening"]' in css
    assert '.core[data-voice-state="thinking"]' in css
    assert '.core[data-voice-state="speaking"]' in css
    assert ".core-spectrum" in css
    assert '.jarvis-ptt[data-provider-ready="false"]' in css
    assert "@media (prefers-reduced-motion: reduce)" in css
