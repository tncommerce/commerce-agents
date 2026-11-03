# DUFYND · Neuer Lieferstandard: Katalog-MVP in großen Wellen

**Owner-Entscheidung 31.10.2026: Ergebnisse und Quantität vor Nachpolitur.**
LIVE STATE GEWINNT · DELTA-ONLY · 0 € Zusatzkosten · keine Doppelarbeit.

## Geschäftsziel und Messung

Hauptziel sind **viele korrekte öffentliche Duftprofile, tatsächlich nutzbare
Händlerangebote, qualifizierter Traffic und die erste im Originalnetzwerk
bestätigte Provision**. Keine Bewertung nach Commit-Zahl, Stundenzahl
oder Design-Sprints.

Getrennte Kennzahlen:

- **Information:** Zahl einzigartiger öffentlicher Duftprofile mit exakter
  Marke, Name, Konzentration, Füllmenge, belegter Kurzbeschreibung,
  dokumentierten Duftnoten und zwei sichtbaren Quellen.
- **Commerce:** Zahl tatsächlich kaufbarer, variantenrichtiger Angebote
  mit aktiven Kaufbedienelementen, gültigen Trackingrechten,
  Endpreisen und quellzeitbasiertem 72-Stunden-Nachweis.
- **Ergebnis:** reale Produktseitenaufrufe, echte Angebotsöffnungen,
  organische Händlerclickouts und *ausschließlich aus Awin/CJ*
  belegte Provisionen.

## Drei unabhängige Produktionsspuren

**A. Facts-only Duftkatalog (höchste Priorität):** Eine öffentliche
redaktionelle Seite benötigt **kein Affiliateangebot und kein lizenziertes
Originalflakon-Foto**. Die neutrale eigene Studio-Illustration bleibt
deutlich als Illustration gekennzeichnet. Fehlende Originalfotos/Angebote
werden nicht als Preise, Stock oder Rechte dargestellt. Duftpyramiden
nur wenn explizit dokumentiert; sonst ehrliche Schlüsselnotenliste.
Keine erfundenen Produktmerkmale, Bewertungen, EANs oder Duftnoten.

**B. Commerce (unabhängiger Zusatz):** Vorhandene Händlerquellen
für exakt ausgewählte Varianten prüfen. Keine Preis- oder Verfügbarkeitsdaten
aus einer bloßen Feedzeile ableiten. Produktangebot nur nach dem
separaten Angebots-/Datenbank-/Release-GO aktivieren. Bereits vorhandene
Rabanne-Strecke nicht duplizieren. Keine Tracking-Testclicks.

**C. Wachstum und Bilder (parallel):** Originalbilder nach tatsächlicher
Asset-/Variantengültigkeit und Rechteumfang aufnehmen. Keine
Bildrechts-Anforderung als Block für neutrale Faktenprofile.
Social-Posts müssen zu passenden öffentlichen Produktseiten führen,
ohne falsche Angebote zu versprechen.

## Liefergröße und Abnahme

Die bestehende Qualifikationsquelle enthält **41 geprüfte, bisher
nicht öffentlich freigegebene Faktenprofile**. Sie werden genau einmal
in **Welle 1: 20** und **Welle 2: 21** aufgeteilt, ohne Doppelungen
zu den 37 öffentlichen Duftprofilen. Die aus den beiden Originalquellen
erzeugten Prüfdateien sind:
- `examples/retail/data/dufynd_facts_wave_01_review.json`
- `examples/retail/data/dufynd_facts_wave_02_review.json`

`python -m scripts.build_dufynd_facts_only_waves --verify-committed`
prüft reproduzierbar beide Wellen. Es wird weder veröffentlicht
noch ein Produkt importiert. Eigentlicher Webseiten-Release bleibt
**ein eigener, an die geprüften Quellen gebundener Sammelauftrag**
für eine **vollständige Welle**, nicht 20 Einzelaufträge.

**MVP-Mindeststandard = harte Go/No-Go-Kriterien:**
exakte Variante und Identität, belegte Duftnoten, korrekte Quellen,
keine irreführenden Fotos oder Preise, korrekte Links, technische
QA/CI, rechtmäßige und ausdrücklich genehmigte Veröffentlichung.

**Darf nach dem ersten Release verbessert werden:**
zusätzliche Duftgeschichten und längere Beschreibungen,
aufwendige Originalfotos, ergänzende Filter, 3D, Animationen
und kosmetisches Feintuning. Kreative Qualität bleibt wichtig,
wird aber nicht zum erneuten allgemeinen Freigabestau.

## Vor jeder öffentlichen Welle

1. Read-only Inventur: Existiert die Variante schon live? Gleichen
   Exakt-Variantenfelder, Quell-Digests und Review-Manifeste ab?
2. Vollständige **Welle in einem PR** vorbereiten, klare öffentlich
   sichtbare Fakten und neutrale Studiokarte. Keine Angebotspreise.
3. CI und repräsentative Mobil-/Desktop-Prüfung bestehen; sämtliche
   erzeugten statischen Pfade im Test eindeutig und erreichbar.
4. **Ein konkretes Owner-Sammel-GO für die Veröffentlichung dieser
   nachprüfbaren 20 bzw. 21 Profile** einholen. Die bisherige
   generelle Zustimmung zu schnelleren Arbeitsblöcken ersetzt dieses
   Veröffentlichungs-GO nicht.
5. Bei nachgewiesenen 0 € Zusatzkosten genau einen kontrollierten
   Static-Storefront-Release durchführen; keine API-/DB-Änderungen
   ohne separaten Auftrag.
6. Live-URLs, Counts und SEO-Kennzeichnung prüfen. Fertig = öffentlich
   erreichbar, nicht nur PR oder vorbereitete Seiten.

Falls ein einzelner Datensatz unzutreffend ist: **nur diesen Datensatz
in HOLD**, den Rest einer bereits autorisierten Welle weiterführen,
solange die Owner-Freigabe ausdrücklich den abgesicherten Teilausfall
erlaubt. Nie fehlende Fakten raten.

## Reporting und Vermeidung von Kleinarbeit

Ein kompakter Ergebnisbericht pro abgeschlossener Welle:
`vorher → nachher öffentliche Profile | neue Angebote | echte Besucher/Clickouts | bestätigte Provisionen | konkrete Blocker`.

Keine erneute allgemeine Designrunde und keine detaillierten
Planungslisten als Ersatz für Umsetzung. Bei externen Blockern
sofort an der anderen unabhängigen Produktionsspur arbeiten.
0 € Zusatzkosten bleibt verbindlich.

## Aktueller Stand zum Entscheidungsdatum

37 öffentliche Duftprofile, 41 source-geprüfte und noch
nicht veröffentlichte Kandidaten, zwei vorbereitete
Kaufangebotstabellen mit **0 Angebotsdatensätzen**.
Die getrennte Freigabe für neue Affiliate-Produktangebote und
Fotorechte bleibt ausdrücklich bestehen. Historische
Netzwerk-/Preis-Snapshots niemals als aktuelle Live-Belege ausgeben.
