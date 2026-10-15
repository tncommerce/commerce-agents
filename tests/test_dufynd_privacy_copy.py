from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVACY = ROOT / "examples/retail/storefront-web/app/datenschutz/page.tsx"


def test_privacy_notice_matches_consent_and_clickout_runtime() -> None:
    text = PRIVACY.read_text(encoding="utf-8")

    for expected in (
        "Nur wenn du „Analyse erlauben“ ausgewählt hast",
        "Eine kopierte Weiterleitungs-URL ist deshalb kein Zustimmungsnachweis",
        "wird das optionale Analyseereignis verworfen",
        "Art. 6 Abs. 1 lit. a DSGVO",
        "älter als 90 Tage",
        "älter als 30 Tage",
        "höchstens 180 Tage",
    ):
        assert expected in text

    for stale in (
        "Zusätzlich protokolliert DUFYND beim Öffnen eines Händlerlinks einen Clickout-Datensatz",
        "Clickout-Ereigniskennung an das jeweilige Partnernetzwerk",
        "Analyse- und Clickout-Ereignisse ersatzweise in lokalen Protokolldateien",
    ):
        assert stale not in text
