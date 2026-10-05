"""Static safety contract for DUFYND Jarvis Live Interface V3."""


def room_text(filename):
    with open(
        "examples/retail/api/control_room/" + filename,
        encoding="utf-8",
    ) as handle:
        return handle.read()


def voice_text():
    js = room_text("room.js")
    start = js.index("// JARVIS LIVE INTERFACE V3")
    end = js.index("  function missions()", start)
    return js[start:end]


def test_one_tap_control_is_explicit_and_bounded():
    html = room_text("index.html")
    assert 'id="jarvis-ptt"' in html
    assert 'aria-pressed="false"' in html
    assert "TAP TO TALK" in html
    assert "Einmal tippen oder V" in html
    assert "Signalton = sprechen" in html
    assert "JARVIS V3" in html
    assert "Mikrofon nur beim Zuhören" in html
    assert "Folgefragen bis 90 s" in html
    assert "PUSH TO TALK" not in html
    assert "Audio nur während gedrückter Taste" not in html


def test_v3_uses_same_origin_webrtc_semantic_turns_and_warm_followups():
    voice = voice_text()

    assert "navigator.mediaDevices.getUserMedia" in voice
    assert "new RTCPeerConnection()" in voice
    assert 'createDataChannel("oai-events")' in voice
    assert 'fetch("/internal/jarvis/voice/session"' in voice
    assert '"Content-Type": "application/sdp"' in voice
    assert '"X-CSRF-Token": csrf' in voice
    assert 'stage.dataset.voiceEnabled === "true"' in voice
    assert 'type: "input_audio_buffer.clear"' in voice
    assert '"input_audio_buffer.speech_started"' in voice
    assert '"input_audio_buffer.speech_stopped"' in voice
    assert "playReadyTone" in voice
    assert 'button.addEventListener("click", requestTurn)' in voice
    assert 'event.code !== "KeyV"' in voice
    assert "pointerdown" not in voice
    assert "pointerup" not in voice
    assert "setTimeout(() => cleanupSession(), 90000)" in voice
    assert 'stage.dataset.sessionWarm = "true"' in voice
    assert "track.enabled = false" in voice
    assert "track.enabled = true" in voice
    assert "25000" in voice
    assert "30000" in voice
    assert "MAX_RESPONSE_OUTPUT_TOKENS = 4096" in voice
    assert "RECOVERY_OUTPUT_TOKENS = 1024" in voice
    assert "max_output_tokens: MAX_RESPONSE_OUTPUT_TOKENS" in voice
    assert '"VOICE LIMIT"' in voice
    assert '"SCHLIESST AB"' in voice
    assert '"TECHNISCHE FORTSETZUNG' in voice
    assert "limitRecoveriesThisTurn < 1" in voice
    assert "armResponseStartTimeout" in voice
    assert '"MIKROFON BLOCKIERT"' in voice
    assert '"REALTIME TIMEOUT"' in voice
    assert "peer.localDescription?.sdp || offer.sdp" in voice
    assert "api.openai.com" not in voice
    assert "OPENAI_API_KEY" not in voice


def test_v3_live_inspector_is_rich_bounded_and_read_only():
    voice = voice_text()

    assert "DUFYND-LIVE-ORIENTATION" in voice
    assert "inspect_dufynd" in voice
    assert "inspectionPayload" in voice
    assert '"workers"' in voice
    assert '"missions"' in voice
    assert '"owner_actions"' in voice
    assert '"first_money"' in voice
    assert '"systems"' in voice
    assert '"risks"' in voice
    assert '"recent_activity"' in voice
    assert "function_call_output" in voice
    assert '"advance_dufynd_safe_work"' in voice
    assert 'fetch("/internal/jarvis/truth"' in voice
    assert '"first_money"' in voice
    assert '"systems"' in voice
    assert "executeTruthInspection" in voice
    assert "await executeTruthInspection(area, focus)" in voice
    assert '"authoritative_truth_unavailable"' in voice
    assert "Nicht spekulieren." in voice
    assert 'fetch("/internal/jarvis/safe-action"' in voice
    assert 'JSON.stringify({ action: "advance_next_safe_work" })' in voice
    assert '"X-CSRF-Token": csrf' in voice
    assert '"HANDELT"' in voice
    assert 'tool_choice: allowAnotherTool ? "auto" : "none"' in voice
    assert "async function handleRealtimeEvent" in voice
    assert "await answerToolCalls(event.response)" in voice
    assert ".slice(0, 12000)" in voice
    assert "safeText" in voice
    assert "safeSha" in voice
    assert "safeCount" in voice
    assert "reason:" in voice
    assert "next_step:" in voice
    assert "owner_action:" in voice
    assert "checkpoint:" in voice
    assert "decision_token" not in voice
    assert "action_token" not in voice
    assert "advance_next_safe_work" in voice
    assert 'type: "response.cancel"' in voice
    assert 'type: "output_audio_buffer.clear"' in voice


def test_v3_keeps_playback_drain_safe():
    voice = voice_text()

    assert "startOutputAnalysis(event.streams[0])" in voice
    assert "drawOutputSpectrum" in voice
    assert "keepPlaybackAliveAfterResponse" in voice
    assert "responseGenerationDone" in voice
    assert "lastAudibleAt" in voice
    assert "response.output_audio.done" in voice
    assert "responseAudioDurationMs" not in voice
    assert "output_token_details?.audio_tokens" not in voice
    assert "finishAfterPlayback(event)" not in voice
    assert "outputSilentFrames >= 72" not in voice
    assert "setTimeout(() => cleanupSession(), 2600)" not in voice


def test_voice_animation_respects_reduced_motion_and_warm_state():
    css = room_text("room.css")
    assert "JARVIS LIVE INTERFACE V3" in css
    assert '.core[data-voice-state="listening"]' in css
    assert '.core[data-voice-state="thinking"]' in css
    assert '.core[data-voice-state="speaking"]' in css
    assert ".core-spectrum" in css
    assert '.jarvis-ptt[data-provider-ready="false"]' in css
    assert '[data-session-warm="true"]' in css
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_v33_dashboard_exposes_operational_diagnosis_and_master_labels():
    html = room_text("index.html")
    js = room_text("room.js")
    assert 'id="diagnosis"' in html
    assert "Warum arbeitet DUFYND gerade" in html
    assert "MASTER ACTION CENTER" in html
    assert "MASTER DECISIONS" in html
    assert "diagnosis-reason" in js
    assert "diagnosis-next" in js
    assert "geparkt, nicht global blockierend" in js
