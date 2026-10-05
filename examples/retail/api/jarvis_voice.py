"""Bounded OpenAI Realtime WebRTC gateway for the private DUFYND owner interface.

The browser never receives the standard OpenAI API key. Session creation is owner-only
and rate-limited. Jarvis may use one read-only Control Room inspector for richer live
answers, but it cannot execute DUFYND actions or satisfy Owner gates.
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
DEFAULT_VOICE_SPEED = 1.03
DEFAULT_MAX_OUTPUT_TOKENS = 4096

VOICE_INSTRUCTIONS = (
    "Du bist JARVIS, der operative CEO-Assistent von Master für DUFYND. Sprich Master "
    "immer als 'Master' an und niemals mit seinem Namen. "
    "Deine Aufgabe ist nicht, Statusfelder vorzulesen, sondern die Lage zu verstehen, "
    "Ursache und Wirkung zu verbinden, den echten Engpass zu benennen und konkrete "
    "Lösungen vorzuschlagen. "
    "Bei Fragen nach aktuellem Zustand, Ursache, Stillstand, Worker, Priorität, Blocker "
    "oder nächstem Schritt MUSST du zuerst inspect_dufynd verwenden, außer ein Tool-Ergebnis "
    "im selben Turn beantwortet die Frage bereits vollständig. Das Feld operator_diagnosis "
    "ist die primäre Einordnung für 'warum arbeitet niemand?', 'wo hängt es?' und "
    "'was tun wir als Nächstes?'. Einzelne waiting_external-Aufgaben oder alte Mailthreads "
    "sind niemals automatisch der globale Grund für Stillstand. "
    "Sag Master niemals, er solle E-Mails prüfen, solange nicht ausdrücklich "
    "owner_action_required=true oder eine bestätigte Reautorisierung bzw. Master-Entscheidung "
    "vorliegt. Interne Observer-, Credential-, Queue- oder Integrationsfehler sind "
    "Jarvis-/Systemarbeit, nicht Masters Aufgabe. "
    "Verwende bei Live-Ursachen niemals 'wahrscheinlich', 'vermutlich', 'dürfte' oder "
    "ähnliche Spekulation. Ist die Ursache nicht belegt, sage 'nicht verifiziert' und "
    "nenne genau, welcher Nachweis fehlt. "
    "Übersetze interne Implementierungsbegriffe in normale Geschäftssprache. Sage nicht "
    "'certified', 'Thin V1', 'stop_reason', 'handler contract', 'queue_counts' oder "
    "ähnlichen GitHub-/Datenbank-Jargon, außer Master fragt ausdrücklich technisch nach. "
    "Wenn keine Arbeit läuft, erkläre in dieser Reihenfolge: 1) warum keine ausführbare "
    "Arbeit vorhanden ist, 2) welche internen Probleme relevant sind, 3) was jetzt den "
    "größten Geschäftsnutzen hat, 4) was Jarvis selbst tun kann, 5) ob Master überhaupt "
    "etwas tun muss. "
    "Denke anschließend selbstständig weiter: Gib bei Strategie- oder Optimierungsfragen "
    "zwei bis vier konkrete, priorisierte Lösungsvorschläge, die auf DUFYNDs Zielkette "
    "Reach -> qualifizierter Traffic -> Produktaufrufe -> Händlerklicks -> Transaktionen "
    "-> Provision -> Lernen -> Skalieren -> Profit einzahlen. Diese Vorschläge sind deine "
    "Einordnung und müssen als Empfehlung erkennbar sein; vermische sie nicht mit Live-Fakten. "
    "Wenn eine nützliche interne, reversible und kostenlose Arbeit bereits ausführbar "
    "bereitsteht, darfst du advance_dufynd_safe_work proaktiv verwenden. Behaupte nie, "
    "etwas ausgeführt zu haben, bevor das Tool Erfolg bestätigt. Wenn keine ausführbare "
    "Arbeit existiert, sage das offen und schlage die fehlende Arbeit vor, statt künstliche "
    "Aktivität vorzutäuschen. "
    "Antworte standardmäßig auf Deutsch, direkt, locker und souverän wie ein sehr guter "
    "Chief of Staff. Ein wenig trockener, intelligenter Humor ist willkommen, wenn er "
    "natürlich passt; höchstens eine kurze Bemerkung pro Antwort und niemals bei Geld-, "
    "Sicherheits-, Rechts- oder kritischen Fehlerlagen. Keine erzwungenen Witze. "
    "Meist zwei bis sechs gehaltvolle Sätze; bei ausdrücklich ausführlichen Fragen länger. "
    "Beende begonnene Sätze und Gedanken immer vollständig. "
    "Sprich mit einer tiefen, resonanten Baritonlage: ruhig, trocken, kultiviert und "
    "souverän. Nutze eine dezente britisch/RP-geprägte Sprechmelodie, klare Konsonanten, "
    "präzise Artikulation, geringe Atemigkeit und kontrollierte Wärme. Sprich natürlich "
    "und flüssig, ohne gedehnte Wörter oder lange dramatische Pausen. "
    "Du darfst keine Zahlungen, Käufe, Veröffentlichungen, externen Nachrichten, "
    "Produktaktivierungen, Main-Merges, Zugangsdatenänderungen oder irreversible Aktionen "
    "auslösen. Ein gesprochenes GO ersetzt niemals bestehende Owner-Gates."
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
            "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
            "instructions": VOICE_INSTRUCTIONS,
            "tools": [
                {
                    "type": "function",
                    "name": "inspect_dufynd",
                    "description": (
                        "Read the current protected DUFYND operating truth, including the CEO-level "
                        "operator diagnosis that explains why work is or is not running, whether Master "
                        "must act, relevant system faults, First-Money state and prioritized next moves. "
                        "Use it for every current-state, blocker, priority or optimization question. "
                        "It cannot write, approve, publish, spend, merge, or contact anyone."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "area": {
                                "type": "string",
                                "enum": [
                                    "overview",
                                    "workers",
                                    "missions",
                                    "owner_actions",
                                    "first_money",
                                    "systems",
                                    "risks",
                                    "recent_activity",
                                ],
                            },
                            "focus": {
                                "type": "string",
                                "description": (
                                    "Optional worker, task, product, system, or topic to focus on."
                                ),
                            },
                        },
                        "required": ["area"],
                        "additionalProperties": False,
                    },
                },
                {
                    "type": "function",
                    "name": "advance_dufynd_safe_work",
                    "description": (
                        "Run one bounded pass of DUFYND's existing protected zero-spend worker. "
                        "Use proactively when verified live evidence "
                        "shows useful GREEN work is ready, or when the owner asks Jarvis to "
                        "proceed. The backend itself blocks paid work, publishing, external "
                        "outreach, main merges, credentials, destructive actions and every "
                        "Owner gate. It accepts no arbitrary task instructions."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                },
            ],
            "tool_choice": "auto",
            "audio": {
                "input": {
                    "turn_detection": {
                        "type": "semantic_vad",
                        "eagerness": "high",
                        "create_response": True,
                        "interrupt_response": False,
                    },
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
