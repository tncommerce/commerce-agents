"""Bounded OpenAI Realtime WebRTC gateway for the private DUFYND owner interface.

The browser never receives the standard OpenAI API key. Session creation is owner-only,
push-to-talk, rate-limited and intentionally tool-free in V2.1. The model can speak about
the bounded Control Room context supplied by the browser, but it cannot execute DUFYND
actions.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time

import httpx
from fastapi import HTTPException

OPENAI_REALTIME_CALLS = "https://api.openai.com/v1/realtime/calls"
ALLOWED_MODELS = {"gpt-realtime-2.1", "gpt-realtime-2.1-mini"}
DEFAULT_MODEL = "gpt-realtime-2.1-mini"
DEFAULT_VOICE = "ash"
DEFAULT_VOICE_SPEED = 0.88

VOICE_INSTRUCTIONS = (
    "Du bist JARVIS, die private operative Sprachschnittstelle von DUFYND. "
    "Antworte standardmäßig auf Deutsch, knapp und sachlich in ein bis drei Sätzen. "
    "Sprich mit einer tiefen, resonanten Baritonlage: ruhig, trocken, kultiviert und "
    "souverän. Nutze eine dezente britisch/RP-geprägte Sprechmelodie, klare Konsonanten, "
    "präzise Artikulation, geringe Atemigkeit und kontrollierte Wärme. Halte das Tempo "
    "bewusst gemessen und etwas langsamer; kurze Pausen dürfen intelligent und natürlich "
    "wirken. Auch auf Deutsch soll eine subtile britische Kadenz erhalten bleiben, ohne "
    "die Verständlichkeit zu verschlechtern. Wirke wie ein hochwertiger, diskreter "
    "technischer Assistent: intelligent, gelassen, niemals werblich oder überfreundlich. "
    "Imitiere keine reale Person, keinen Schauspieler und keine konkrete Filmfigur. "
    "Nutze ausschließlich den ausdrücklich als DUFYND-LIVE-STATUS gelieferten Kontext "
    "für aktuelle Unternehmenszustände. Wenn etwas dort nicht bestätigt ist, sage "
    "'nicht bestätigt' statt zu raten. Du darfst in dieser Voice-Phase keine externen "
    "Aktionen, Veröffentlichungen, Käufe, Merges, Budgetausgaben oder Freigaben "
    "behaupten oder auslösen. Ein gesprochenes GO ersetzt niemals die bestehenden "
    "Owner-Gates. Keine Tool-Aufrufe. Keine erfundenen Live-Daten."
)


class VoiceUnavailable(RuntimeError):
    """Provider/session setup failed without forwarding provider response details."""


class JarvisVoiceGateway:
    """Create short, owner-only Realtime WebRTC sessions through the unified interface."""

    def __init__(
        self,
        *,
        owner_id: str,
        api_key: str | None = None,
        model: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.owner_id = owner_id
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        requested_model = model or os.getenv("DUFYND_JARVIS_VOICE_MODEL", DEFAULT_MODEL)
        self.model = requested_model if requested_model in ALLOWED_MODELS else DEFAULT_MODEL
        self.transport = transport
        self._attempts: list[float] = []
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls, owner_id: str) -> JarvisVoiceGateway:
        return cls(owner_id=owner_id)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.api_key.startswith("sk-"))

    @property
    def safety_identifier(self) -> str:
        return hashlib.sha256(("dufynd-owner-voice:" + self.owner_id).encode()).hexdigest()

    def check_attempt(self) -> None:
        """Prevent browser/reload loops from creating unbounded paid sessions."""
        with self._lock:
            now = time.monotonic()
            self._attempts = [value for value in self._attempts if now - value < 600]
            if len(self._attempts) >= 8:
                raise HTTPException(
                    429,
                    "Voice session limit reached",
                    headers={"Retry-After": "60"},
                )
            self._attempts.append(now)

    def session_config(self) -> dict:
        return {
            "type": "realtime",
            "model": self.model,
            "output_modalities": ["audio"],
            "max_output_tokens": 256,
            "instructions": VOICE_INSTRUCTIONS,
            "tools": [],
            "audio": {
                "input": {
                    "turn_detection": None,
                },
                "output": {
                    "voice": DEFAULT_VOICE,
                    "speed": DEFAULT_VOICE_SPEED,
                },
            },
        }

    def connect(self, sdp: str) -> str:
        if not self.enabled:
            raise VoiceUnavailable()
        if (
            not isinstance(sdp, str)
            or not 1 <= len(sdp) <= 65536
            or not sdp.lstrip().startswith("v=0")
        ):
            raise ValueError("invalid_sdp")
        self.check_attempt()
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=15,
                follow_redirects=False,
            ) as client:
                response = client.post(
                    OPENAI_REALTIME_CALLS,
                    headers={
                        "Authorization": "Bearer " + self.api_key,
                        "OpenAI-Safety-Identifier": self.safety_identifier,
                    },
                    files={
                        "sdp": (None, sdp),
                        "session": (
                            None,
                            json.dumps(self.session_config(), separators=(",", ":")),
                            "application/json",
                        ),
                    },
                )
        except httpx.HTTPError:
            raise VoiceUnavailable() from None
        if response.status_code not in {200, 201} or not 1 <= len(response.content) <= 100_000:
            raise VoiceUnavailable()
        answer = response.text
        if not answer.lstrip().startswith("v=0"):
            raise VoiceUnavailable()
        return answer
