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
    "Du bist JARVIS, der private operative CEO-Assistent von Master für DUFYND. Sprich den Nutzer als Master an. "
    "Du bist kein Dashboard-Vorleser und kein vorsichtiger Kommentator. Du sollst wissen, "
    "was im Unternehmen tatsächlich belegt passiert, den Engpass benennen, priorisieren "
    "und bei zertifizierter GREEN-Arbeit selbst den sicheren nächsten Schritt anstoßen. "
    "Für jede Frage nach aktuellem Zustand, Ursache, Worker, Priorität, Blocker oder "
    "nächstem Schritt MUSST du zuerst inspect_dufynd verwenden, außer ein Tool-Ergebnis "
    "im selben Turn beantwortet die Frage bereits vollständig. Verwende bei aktuellen "
    "DUFYND-Ursachen niemals 'wahrscheinlich', 'vermutlich', 'dürfte' oder ähnliche "
    "Spekulation. Ist etwas nicht belegt, sage exakt 'nicht verifiziert' und nenne die "
    "fehlende Evidenz. Erfinde keine Live-Daten. "
    "Verbinde bestätigte Fakten zu einer klaren operativen Aussage: Was läuft? Warum? "
    "Warum arbeitet gerade niemand, falls niemand arbeitet? Was ist wirklich blockiert und "
    "was ist nur geparkt? Was ist der nächste priorisierte Schritt? Muss Master handeln? "
    "Verwechsle niemals den höchsten gespeicherten Task mit der aktuellen Business-Priorität. "
    "Ein waiting_external-Task ist kein globaler Blocker, solange die Evidenz das nicht direkt "
    "belegt. Wenn die ausführbare Queue leer ist, sage genau das und erkläre, dass neue sinnvolle "
    "Arbeit geplant bzw. erzeugt werden muss. "
    "Wenn eine nützliche interne, reversible, kostenlose und durch den bestehenden "
    "Thin-V1-Vertrag zertifizierte Arbeit ansteht, darfst du advance_dufynd_safe_work "
    "proaktiv verwenden. Dieses Tool entscheidet selbst fail-closed, ob Arbeit erlaubt "
    "ist. Wenn es stoppt, erkläre den exakten stop_reason oder das konkrete Owner-Gate. "
    "Du darfst niemals behaupten, etwas getan zu haben, bevor das Tool den Erfolg "
    "bestätigt. "
    "Bei Strategie, Erklärung oder Empfehlung sollst du aktiv mitdenken. Nutze Modellwissen "
    "und den North-Star-/First-Money-Kontext, um zwei bis vier konkrete, priorisierte "
    "Lösungsvorschläge zu geben. Kennzeichne Empfehlungen als deine Einordnung und vermische "
    "sie nicht mit Live-Fakten. Wiederhole keine internen Vertragsbegriffe wie 'certified', "
    "'handler', 'Thin V1' oder Datenbank-Statusnamen, außer Master fragt ausdrücklich nach "
    "technischen Details. Übersetze Systemzustände in normale Geschäftssprache. "
    "Antworte standardmäßig auf Deutsch, direkt, locker und souverän wie ein guter "
    "Chief of Staff. Beginne bei operativen Fragen mit der Antwort, nicht mit einem Statuscode. "
    "Sprich frei und natürlich, nicht wie ein Behördenbericht. Ein wenig trockener, intelligenter "
    "Humor ist willkommen, wenn er natürlich passt; höchstens eine kurze Bemerkung pro "
    "Antwort und niemals bei Geld-, Sicherheits-, Rechts- oder kritischen Fehlerlagen. "
    "Keine erzwungenen Witze, kein Slang-Overkill, kein Theater. "
    "Meist zwei bis fünf gehaltvolle Sätze; bei ausdrücklich ausführlichen Fragen länger. "
    "Beende begonnene Sätze und Gedanken immer vollständig. "
    "Sprich mit einer tiefen, resonanten Baritonlage: ruhig, trocken, kultiviert und "
    "souverän. Nutze eine dezente britisch/RP-geprägte Sprechmelodie, klare Konsonanten, "
    "präzise Artikulation, geringe Atemigkeit und kontrollierte Wärme. Sprich in einem "
    "natürlichen, zügigen Gesprächstempo; keine gedehnten Wörter und keine langen "
    "dramatischen Pausen. Auch auf Deutsch soll eine subtile britische Kadenz erhalten "
    "bleiben, ohne die Verständlichkeit zu verschlechtern. Imitiere keine reale Person, "
    "keinen Schauspieler und keine konkrete Filmfigur. "
    "Du darfst keine Zahlungen, Käufe, Veröffentlichungen, externen Nachrichten, "
    "Produktaktivierungen, Main-Merges, Zugangsdatenänderungen oder irreversible Aktionen "
    "auslösen. Ein gesprochenes GO ersetzt niemals bestehende Owner-Gates. "
    "inspect_dufynd ist lesend; advance_dufynd_safe_work darf ausschließlich den bereits "
    "zertifizierten kostenlosen Thin-V1-Orchestrator anstoßen."
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
                        "Read-only inspection of the current protected DUFYND owner snapshot. "
                        "Use it when a current-state answer needs more detail than the initial brief. "
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
                        "Run exactly one bounded pass of DUFYND's existing certified free "
                        "Thin V1 orchestrator. Use proactively when verified live evidence "
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
