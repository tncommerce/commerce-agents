# DUFYND · Datenbetrieb statt PR pro Händlerpreis (DEV / nicht live)

## 27.10.2026 – Alternativer Awin Enhanced-/Google-Feed (nur Feldprüfung)

Awin dokumentiert einen separaten Enhanced-/Google-Retail-Feed im JSONL-Format
mit möglichen Feldern \`id\`, \`gtin\`, \`size\`, \`unit_pricing_measure\`,
\`availability\`, \`price\` und \`shipping\`. **Ob der konkrete Advertiser
Top Parfümerie 31081 im Konto 3099222 einen solchen Feed bereitstellt,
ist bisher NICHT bestätigt.** Die offizielle Awin-Spezifikation ist nur
ein Formatvertrag, kein gültiger produktbezogener Preis- oder Lizenzbeleg.

Für eine möglicherweise bereitgestellte *lokale, autorisiert erworbene*
JSONL-Datei gibt es nun die **isolierte Read-only-Quelltriage**:

\`\`\`bash
python scripts/review_dufynd_awin_enhanced_feed.py \
  --feed /privat/authorisierte-original-feed-datei.jsonl \
  --source-receipt /privat/geprüfter-source-receipt.json
\`\`\`

Das Source-Receipt enthält lediglich \`publisher_id=3099222\`,
\`advertiser_id=31081\`, \`source_type=awin_enhanced_retail_jsonl\`,
\`download_sha256\` und das echte \`downloaded_at\`; es ist **kein**
Netzwerk-Token und darf keinen solchen enthalten. Der SHA-256 muss den
unveränderten gesamten JSONL-Bytes entsprechen. Die Vorprüfung nutzt
nur bestehende, freigegebene Top-Händler-SKUs (höchstens 50 pro Durchlauf),
prüft bekannte EAN, genaue ml-Größe, in_stock, eindeutigen EUR-Artikelpreis
ohne ungeklärte Rabatte und die explizit landesweite DE-Versandangabe.
Falsche Größe, fremde GTIN, doppelte SKUs, unbestätigte Versandkosten,
abgelaufene Downloadbelege oder fehlende Händlerfreigaben werden blockiert.

\`FIELD_COMPLETE_REVIEW_ONLY\` bedeutet **niemals** aktivierbar!
Auch bei vollständig gefüllten Feldern kann ein Awin-Download-Zeitstempel
nicht die exakte SKU-Quellbeobachtungszeit ersetzen. Positives
\`prepare_batch()\` und Live-Aktivierung verlangen einen weiteren
belegten, aktuellen Händler-/Netzwerk-Quellvertrag. Die Ausgabe enthält
keine angebotenen Preise, Merchants-URLs, künstlichen Affiliate-Links,
und der neue Parser hat **0 Netzwerkzugriffe, 0 Datenbank-Schreibvorgänge
und 0 öffentliche Angebotsaktivierungen**.

Referenzen (reine Dokumentation):
https://help.awin.com/apidocs/retail-publisher-productapidocumentation-1
https://help.awin.com/developers/docs/enhanced-feeds-prod-spec



## 27.10.2026 – Zusätzliche Quellenhärtung: archiviertes Git-Manifest und UVP

Die lokale `--merchant-browser-evidence-dir`-Wiederverwendung ist ausschließlich
für die **zwei bereits verifizierten** 26.10.-Browser-Quellpakete vorgesehen.
Ein selbst erstelltes Verzeichnis oder eine neue `SHA256.json` wird nicht als
vertrauenswürdiger Ursprung akzeptiert. Der ursprüngliche Git-Blob-Hash
des Quellmanifests ist explizit gebunden, jede Browser-/Versanddatei muss
ihren SHA-256-Eintrag erfüllen, und `batch-input.json` muss bytegeprüft
dem übergebenen Original-Batchobjekt entsprechen. Neue Händlerfeeds können
nach separater Quellfreigabe ihren eigenen Batch-Prozess erhalten.

Außerdem darf ein durchgestrichener `UVP`-Preis niemals als
aktueller ausgewählter Variantengesamtpreis gelten. Der Parser prüft
genau eine tatsächliche Preiszeile im ausgewählten SKU-Abschnitt
und ignoriert UVP und Literpreise.

Diese Härtung verändert keine der ursprünglichen 10 Datenpunkte,
keine Live-Angebote, keine ausgeführten Verkäufe oder Provisionen.
Testfälle für fremde Quellen, geänderte Batch-Metadaten und UVP sind
hinzugefügt, auf diesem exakten GitHub-Head **noch nicht ausgeführt**.


## 27.10.2026 – vorhandene Original-Browser-Batches wiederverwendbar prüfen (DEV)

Der neue optionale CLI-Modus
`--merchant-browser-evidence-dir artifacts/dufynd-top-six-offers-20261026`
(bzw. `dufynd-top-wave2-offers-20261026`) liest **nur** die drei
lokalen SHA-256-archivierten Quelldateien. Das Manifest muss mit deren
unveränderten Bytes übereinstimmen; pro Angebot müssen Quelle, geprüfter
Händlerlink, Händler-SKU, ausgewählte ml-Variante, Preis, positiver
Kaufbutton, Lageranzeige und die **ursprüngliche** `checked_at`-Zeit
zum kanonischen Angebot passen. Der originale Deutschlandversand wird
aus der archivierten Händlerbedingung gemeinsam für den Batch geprüft.
Die Funktion ergänzt den Belegtyp/Zeitstempel **nur im Speicher**,
überschreibt keine historische Quelldatei und verlängert keine Preise.

Für beide Pakete (6 + 4) sind eigene reale Archiv-Fixture-Tests und
SHA-/Zeitänderungs-Negativfälle vorbereitet; kein GitHub-Testlauf auf
dem neuen HEAD ist hiermit behauptet. Browser-Beobachtungen enthalten
keine Echtzeit-Verfügbarkeit für einen späteren Tag, deshalb sperrt der
72h-Quellstempel den Batch nach Ablauf. Ursprüngliche Repo-Quellen
werden nicht automatisch wiederveröffentlicht, und `--apply` bleibt
an die exakte zusätzliche Owner-/Datenbankfreigabe gebunden.


### Käufer-API prüft die gleichen Handelswerte (DEV)

Die Runtime-Entscheidung `apply_runtime_snapshot` akzeptiert eine positive
Supabase-Zeile nun nur mit **Preis + bekannten DE-Versandkosten + `in_stock=true`**.
Ein Datenbank-/Transportfehler, ein HOLD, unbekannter Versand oder ein explizit
nicht verfügbarer Artikel ergeben für Listing **und** Clickout
`None`/kein Angebot. Damit kann kein unvollständiges Datenbankobjekt die
strengeren Importer- und SQL-Check-Regeln umgehen. Das gilt nur, falls der
Runtime-Modus nach einem späteren, eigenständig genehmigten Release
überhaupt aktiviert wird. Noch keine Produktion umgestellt.


## 27.10.2026 – Positivnachweise an Original-Beobachtungszeit binden (DEV)

Auch ein formal gültiger Batch darf **keine alten Preisdaten neu datieren**.
Ein `verified`-Satz erfordert daher ab diesem Entwicklungsschritt im
bestehenden `evidence`-Objekt einen genauen
`source_observed_at`-Zeitpunkt, der mit `verified_at` übereinstimmt,
sowie einen quelltypspezifischen Originaldigest und Belegtyp:

- `direct_merchant_review`: `source_evidence_kind=selected_variant_page`,
  `browser_observation_sha256` (64 Hexzeichen);
- `official_network_feed`:
  `source_evidence_kind=exact_sku_stock_price_shipping_row`,
  `source_row_sha256`;
- `authorized_merchant_api`:
  `source_evidence_kind=authorized_exact_sku_response`,
  `api_observation_sha256`.

Die strukturelle Prüfung bestätigt **nicht** selbst die Händler-Autorisierung
oder Byte-Integrität: Der Operator muss vor dem separaten exakten Batch-GO
Originalsource und Hash tatsächlich abgleichen. `Last Imported` einer
Feedliste ist ausdrücklich **kein** solcher per-SKU-Preis-/Bestandsnachweis.
Die zehn am 26.10. archivierten Quellpakete behalten ihre ursprünglichen
Hash-/Zeitstempel und werden **nicht** nachträglich verändert oder verlängert.
Ein bewusstes `hold` ohne Preis/Bestandsbehauptung bleibt auch ohne
positiven Händler-Zeitstempel möglich.

Regressionen für alte Zeitstempel, falsche Hash-/Belegfelder, reine
Feed-Import-Zeit und fail-closed HOLD sind vorbereitet. **Kein Live-Rollout
oder neue 72h-Frische durch diese Änderung.**


## 27.10.2026 – Sammelprüfung und wahrheitsgemäße HOLD-Sperren (DEV / nicht live)

**Ziel:** Eine Quelle für mehrere Händlerangebote prüfen, statt für jeden Duft
einen eigenen Git-Release oder einen künstlich verlängerten Preissnapshot zu erzeugen.

- \`scripts/prepare_dufynd_runtime_offer_batch.py --evidence <batch.json> --triage\`
  erzeugt für **1–50 eindeutige Angebots-IDs** einen einzigen lokalen,
  nicht schreibenden Bericht: \`COMPLETE_EVIDENCE_REVIEW_ONLY\`,
  \`HOLD_REVIEW_ONLY\` oder \`BLOCKED_SOURCE_EVIDENCE\` mit festem
  Fehlercode. Die Auswertung druckt weder Händler-/Affiliate-URLs noch
  alte Preise, Quelltexte oder Geheimnisse. **Auch vollständig plausible
  Kandidaten werden dadurch nicht aktiviert.**
- Ein \`verified\`-Datensatz benötigt eine aktuell unabhängig belegte exakte
  Variante, verifizierte offizielle Affiliate-Route, **positiven Bestand,
  Preis und bestätigten DE-Versand**. Ein neuer Feed-Import-Zeitstempel oder
  ein altes Preissignal allein erfüllt das nicht.
- Ein \`hold\`-Datensatz trägt dagegen **keinen Preis, keinen Versandwert
  und keinerlei Behauptung zum Lagerbestand**. Ein expliziter Sperrgrund
  wie \`shipping_unverified\`, \`stock_unverified\` oder
  \`variant_ambiguous\` ist erforderlich und verändert den
  SHA-256-gebundenen Batch-Inhalt. Dies ist eine Quellenentscheidung,
  keine neue positive Händlerfreigabe.
- Die vorbereitete **noch nicht angewandte** Supabase-Migration erzwingt
  die Unterscheidung zusätzlich durch einen SQL-CHECK. Bestehende
  identitätsgebundene Affiliate-URLs, Produkt-IDs und die 72h-Gates
  bleiben unberührt. Ohne \`DUFYND_RUNTIME_OFFER_SNAPSHOTS=enabled\`
  ändert sich die Live-Kaufstrecke nicht.
- Für den 26.10. existieren bereits zwei originale Top-Parfümerie-Batches
  mit **6 + 4** Angebotssätzen. Deren Prüfuhrzeit darf am 27./29.10. nicht
  durch dieses Tool hochgesetzt werden. Sobald ein gesamter Batch später
  vollständig verifiziert ist, bleibt die separate exakte
  \`batch_id:batch_sha256\`-Freigabe Voraussetzung für
  \`--apply\`. Keine Teilaktivierung anhand des Triages.
- Zusätzliche Pytest- und echte PostgreSQL-Fälle sind in den bestehenden
  Testdateien vorbereitet. **Kein neuer CI-Erfolg und keine Live-SQL-
  Migration in diesem DEV-Schritt behauptet.**



Stand: 23.10.2026. Die ersten produktiven Preisquellen bleiben **unverändert**.
Dieses Paket ist eine vorbereitete einmalige Umstellung; es ist **kein** bereits
aktivierter Notino-Feed oder eine Freigabe zur Veröffentlichung.

## 24.10.2026 – zusätzliche Offline-Gates (DEV, nicht veröffentlicht)

**Quellidentität (Awin):** Der authentifizierte Feedlisten-Download bleibt
auf den ursprünglich ausgewählten Publisher-Schlüssel und die exakte Feed-ID
gebunden. Zusätzlich verbietet die Downloadprüfung jetzt zweite
API-Key-Identitäten in Query-Parametern (auch Groß-/Kleinschreibung,
`api_key`/`api-key` und URL-encodete Varianten) und unvollständige
Query-Paare. Ein Redirect auf einen weiterhin erlaubten Awin-Host darf die
Identität nicht über Query-Shadowing austauschen. Die bestehenden legitimen
`format=csv`-/`language=de`-Filter bleiben zulässig. Es fand weder ein
authentifizierter Feeddownload noch ein Token-Test statt.

**Käuferschutz bei kaputten Quelldateien:** Die vollständige veröffentlichte
`merchant_offers.json` wird vor jeder Datenbank-/Käuferabfrage gegen das
bestehende Pydantic-`MerchantOffer`-Schema geprüft. Auch JSON-konforme
`"Infinity"`-Werte für Preis, Versand oder Provision sind ungültig.
Eine fehlerhafte Preis-/Zeit-/Angebotszeile sperrt alle Angebote statt
teilweise ausgelieferte Listings oder HTTP-500-Fehler zu riskieren.
Eine reine read-only-Formprüfung der 53 aktuell eingecheckten kanonischen
Zeilen ergab keinen offensichtlichen Typ- oder Datumsfehler; eine vollständige
Repo-Ausführung wurde damit **nicht** ersetzt.

**Regressionen hinzugefügt, noch nicht im Repository ausgeführt:**
`tests/test_dufynd_awin_data_feed_fetch.py` (Query-Credential-Shadowing,
Redirect, zulässige Filter) und `tests/test_dufynd_runtime_offer_snapshots_v1.py`
(nicht-endliche/ungültige Preise, ungültige Versand-/Provisions-/Zeitwerte,
keine partiellen Käuferantworten oder privaten DB-Reads).
Sämtliche neuen GitHub-Commits verwenden `[skip ci]`, weil 0 € für weitere
Actions-Läufe noch nicht unabhängig belegt ist. **Keine grüne CI für diese
neueren Änderungen behaupten.** Vor jedem Produktions-GO: echte autorisierte
Awin-URL-Form ohne Tokenpreisgabe verifizieren, vollständigen Pytest/Ruff- und
PostgreSQL-/Web-CI-Lauf auf *exaktem* HEAD kostenneutral nachweisen sowie
aktuelle CJ-/Notino-Händlerdaten und Medienrechte belegen.

## Bestehender Befund

- 53 freigegebene **kanonische Angebotsdatensätze** bei acht Händlern in
  \`examples/retail/data/merchant_offers.json\`. Der ursprüngliche Preis und
  Bestand darin ist nur eine historische Momentaufnahme.
- Die API sperrt Angebote automatisch nach 72 Stunden; ein fehlendes Angebot
  bedeutet nicht, dass der Duft ausverkauft ist.
- Am 23.10.2026 liefen drei Notino-Snapshots von PR #816 um 19:53:41–43 UTC
  ab. Es ist kein erneuter PR nötig, um diese korrekt auszublenden.
- Der schon vorhandene Supabase-Nachweis für Rabanne aktualisiert nur exakt
  dessen altes Datum. Er ist keine allgemeine Notino-Datenanbindung.
- 37 öffentlich katalogisierte Duftprofile / vier explizit freigegebene
  Originalbildvarianten. Weitere Review-Profile sind keine automatischen
  Publikations- oder Bildlizenzfreigaben.

## Einmalige technische Einführung (gesondertes Owner-Produktions-GO)

1. Security-/Performance-Advisors und Migrations-Diff prüfen; die vorbereitete
   \`supabase/migrations/20261023221100_dufynd_runtime_offer_snapshots_v1.sql\`
   bei einem genehmigten DB-Release auf die bestehende Supabase-Instanz anwenden.
   **In diesem Dev-PR wurde keine DDL auf dem Live-Projekt angewendet.**
2. Tabelle \`dufynd_runtime_offer_snapshots_v1\` besitzt RLS, keine
   \`anon\`/\`authenticated\`-Grants und service-role-beschränkten Lese-/Upsert-Zugang.
   Jedes Update wird atomar auditiert; alte und zukünftige Daten werden abgewehrt.
3. Ein **authentisch** aktuelles Quellpaket mit exakten SKU-/Händler-/Varianten-
   Daten, Preis **plus Versand**, Bestand und ursprünglichem Beobachtungszeitpunkt
   prüfen. Nicht automatisch aus dem heutigen Systemzeitpunkt ableiten.
4. Erst im Dry Run den Batch validieren; pro Batch statt pro SKU freigeben.
   Danach mit exakt passender Batch-ID und Operator-GO eine einzelne atomare
   Datenbank-Upsert-Anfrage ausführen.
5. Die Backend-Option \`DUFYND_RUNTIME_OFFER_SNAPSHOTS=enabled\` erst nach
   erfolgreich befüllter und extern überprüfter Tabelle im vorhandenen Render-
   API-Service setzen. Separates Owner-GO und bestehendes Kostenlimit gelten.
   **Default ist AUS**; kein Endpoint, Link, Preis oder Service ändert sich
   durch das reine Mergen von vorbereitetem Code ohne Aktivierung.

## Täglicher Preisbetrieb **nach** einmaligem Release

\`\`\`sh
# Vorab einen Quell-Evidenz-Batch vorbereiten (keine Netzwerkanfrage).
python -m scripts.prepare_dufynd_runtime_offer_batch \
  --evidence evidence/reviewed-prices-YYYYMMDD.json

# Nur nach Quellprüfung und bestätigter batch-spezifischer Freigabe:
DUFYND_OFFER_BATCH_OWNER_GO=<BATCH-ID>:<BATCH-SHA256> \
python -m scripts.prepare_dufynd_runtime_offer_batch \
  --evidence evidence/reviewed-prices-YYYYMMDD.json \
  --apply --owner-approval <BATCH-ID>:<BATCH-SHA256>
\`\`\`

Das Eingabeformat enthält \`schema_version: 1\`, \`batch_id\` und \`offers\`
(1–50 Einträge). Jeder Eintrag benötigt \`offer_id\`, \`product_id\`,
\`merchant_product_id\`, \`variant_label\`, \`decision: verified|hold\`,
\`price\`, \`shipping_cost\` (nullable = unbekannt, niemals kostenlos
unterstellt), \`in_stock\` (Bool), \`verified_at\` mit Zeitzone,
\`source_type\`, \`source_ref\` und eine \`evidence\`-Map mit
\`source_observation\`. Die Originalquellen-/Aufnahmebestätigung erfolgt
vor der Freigabe; ein SHA-256-Beleg ist für sich allein keine
Rechte-, Bestands- oder Netzwerkbestätigung.

**Unter keinen Umständen** dürfen Produkt-/Affiliate-Ziel-URLs,
Händleridentität oder 50-/90-/100-ml-Varianten aus dem Preisbatch
überschrieben werden. Fehlende/falsche/abgelaufene/gesperrte Datensätze und
Datenbankausfälle führen zu **keiner sichtbaren Kaufoption**. Die
unabhängigen Duftprofile bleiben weiterhin verfügbar. Browser-Analytics
und Rechnungs-/Provisionsdaten werden durch dieses Verfahren nicht simuliert.

Bei Supabase-Unterbrechung gibt es keinen stillen Fallback auf einen
historischen Preis und keinen künstlichen URL-Redirect. Die Laufzeit
liest nur bekannte, vorab freigegebene Angebots-IDs; neue Produktvarianten
und neue Händler benötigen weiterhin einen separaten **gebündelten**
Katalog-/Affiliate-Onboarding-Release.

## Warum das Arbeit spart

- **Datenpflege**: nach einmaliger genehmigter Backend-/DB-Umstellung:
  ein geprüfter Batch mit bis zu 50 Angeboten, eine DB-Transaktion,
  keine GitHub-PRs oder Render-Neudeployments pro Preisveränderung.
- **Software**: neuer Checkout, Sicherheit, Datenbankstruktur und UX
  behalten vollständige CI und funktionale Browserprüfungen.
- **Fotos**: Bildrechte und exakte Variante bleiben eigener Prozess.
  Der vorhandene Batch-Skriptweg
  \`scripts/prepare_dufynd_catalog_photo_wave.py\` nutzt offizielle
  Awin-Feed-/Rechte-Daten. Er darf eine alte Feedquelle nicht als aktuell
  ausgeben. Bilder werden chargenweise geprüft statt gefälscht oder
  einzeln neu programmiert.
- **Katalog**: bestehende 37 öffentliche Profile plus vorbereitete
  Review-Wellen als Warteschlange nutzen. Ein Dufttext kann publiziert sein,
  während Bild- und Händlerangebotssichtbarkeit auf HOLD bleiben.

## Noch offene externe Abhängigkeiten

- Autorisierte aktuelle Notino-/CJ-Produktdatenquelle **nicht verifiziert**.
  Eine bestehende CJ-Mitgliedschaft bedeutet weder aktuellen Lagerbestand
  noch jeden SKU-Link noch Bildrechte.
- Awin Top Parfümerie Feed 91379 besitzt frühere Quell- und Rechte-Evidenz.
  Vor neuen Bildchargen müssen Feed-Aktualität, Advertiser-Zugehörigkeit,
  EAN, Konzentration, Größe und erlaubte Verwendung erneut geprüft werden.
- Aktueller Render-/Supabase-Kostenstand und Live-Deployment benötigen
  eine **separate Owner-Entscheidung**. Keine neuen Abos oder Credits.
- Vor Produktiv-Go: echte zwei-Schritt-Abnahme auf exakt gleichem Release:
  1. Leere/gesperrte/alte/falsche Quellinfos ergeben **0 Kauf-CTAs**.
  2. Eine echte frisch belegte neue SKU-Preisbeobachtung kann aus der
     Datenbank erscheinen, ohne GitHub-/Render-Codeänderung.

Die Arbeit hier ersetzt nicht die Freigabe eines neuen Produkts,
unveränderte genehmigte Affiliate-Ziele oder korrekte Werbung-/Preislabels.


## Ergänzung: skalierbare Evidenz- und Produktprüfung (24.10., nur DEV)

Die autorisierte Händleridentität liegt weiterhin **nicht** im Preisbatch.
Ein als \`verified\` importierter Datensatz benötigt jetzt zusätzlich:
- aktives Händlerprogramm und bereits freigegebenen, unveränderten Affiliate-Link,
- bei eingeschränkten Programmen die freigegebene \`verified_product_scope\`,
- exakte Hersteller-/Marke-, Konzentrations-, Volumen- und GTIN/EAN-Übereinstimmung
  mit \`catalog.json\` und einem als \`verified_current_variant\` gekennzeichneten
  Händler-Mapping. Der neue Quellenbeleg enthält \`brand\`, \`concentration\`,
  \`volume_ml\` (Integer) und \`ean\` (GTIN mit gültiger Prüfziffer).
Fehlt eines der Felder, erfolgt kein automatischer Ersatz durch ausgedachte Werte.
Ein explizites \`hold\` darf ein bereits gespeichertes Angebot weiterhin sperren.

Für neue Bilder/Produkte existiert zusätzlich ein **rein lesender**
10–20-Produkte-Preflight über bereits vorhandene Quellen:

\`\`\`sh
python -m scripts.report_dufynd_commerce_scale_wave --batch-size 20 \
  --output /tmp/dufynd-commerce-review-wave.json
\`\`\`

Optional kann ein frischer, bereits vom vorhandenen offiziellen Awin-Bildskript
erzeugter \`--photo-wave\` mitgegeben werden. Abgelaufene Feed-Metadaten
oder ein ungesichertes Bild werden dadurch nicht freigegeben.
Das Ergebnis trennt Informationsprofil, **bereits** freigegebenes Originalbild
und aktuellen/verifizierungsbedürftigen Händlerbeleg. Erwartete 72h-Abläufe
sind keine API-Störung; nur ein unabhängig nachgewiesenes
\`--api-status unavailable\` wird als technischer Incident markiert.
Ohne Beobachtung ist der API-Status ausdrücklich \`not_checked\`.

Der Report schreibt nicht in Supabase und eröffnet keinerlei Kauf-/Bild-/
Produktfreigabe. Notino- und Awin-Feed-Inhalte werden nicht künstlich
aktualisiert; die externe Quelle bleibt ein separates Qualitäts-Gate.

## Rollout-Isolation + echte Postgres-Tests (24.10., DEV)
Die einmalige Aktivierung nutzt standardmäßig nur `notino` als Runtime-Datenquelle;
weitere Händler können ausdrücklich in `DUFYND_RUNTIME_OFFER_MERCHANTS`
als kommagetrennte kanonische Händler-IDs ergänzt werden. Eine fehlerhafte
Konfiguration stoppt die gesamte Runtime-Angebotsansicht fail-closed.
Ein Quellenausfall sperrt die betroffenen dynamischen Händlerangebote, nicht
den zuvor getrennt zertifizierten Rabanne-Purchase-Evidence-Weg.

Die vorbereitete Migration blockiert beim Update zusätzlich Veränderungen
an Produkt-, Händler-, SKU- und Identitätsmerkmalen auf SQL-Ebene. Ein
dedizierter PostgreSQL-Test läuft innerhalb des vorhandenen
`budget-postgres`-CI-Services, ohne neue DB oder Produktiv-DDL.
Er prüft Rollen/Rechte, 72h, Zeitmonotonie, Identitätssperre, HOLD und Audit.

## Sicherheit der Batch-Freigabe (24.10., DEV)
Ein Freigabe-Batch wird über einen reproduzierbaren SHA-256 des exakten
vorbereiteten Inhalts (inklusive einzelner Quellen-Evidenz-Digests, Preise,
Bestand und Prüfzeitpunkten) gebunden. Im Dry Run wird `batch_sha256`
ausgegeben. Erst `DUFYND_OFFER_BATCH_OWNER_GO=<BATCH-ID>:<BATCH-SHA256>`
**und** `--owner-approval` mit exakt demselben Scope erlauben das
serverseitige Anwenden. Ändert sich auch nur ein Beleg oder Preis nach
Owner-Prüfung, ist die zuvor erteilte Freigabe ungültig.
Der Hash beweist Eingabeintegrität, nicht die Wahrheit oder Herkunft einer
Händlerbeobachtung. Die separate externe Quellprüfung bleibt verpflichtend.

Das Affiliate-Gate verlangt nun zusätzlich den exakten bereits freigegebenen
CJ/Awin-Tracking-Endpunkt mit Zielgleichheit zur veröffentlichten
Produktseite sowie die bekannten Advertiser- und Publisher-IDs. Fremde
Weiterleitungen, zusätzliche URL-Varianten oder falsche Netzwerkprogramme
dürfen nicht durch eine gewöhnliche Preis-Charge eingeschleust werden.

## P2 – Offizielle CJ-Notino-Produktfeed-Erkennung (24.10.2026, read-only)

**Umgesetzt:** \`scripts/check_dufynd_cj_notino_feed.py\`. Es nutzt die
von CJ dokumentierte Publisher-\`productFeeds\`-GraphQL-Abfrage gegen
\`https://ads.api.cj.com/query\`, strikt auf **eine** explizit konfigurierte
Notino-Advertiser-Company-ID begrenzt. Der Report enthält ausschließlich
Feed-Metadaten (adId, Datum, Anzahl, Typ) und **keine Preise, Links oder
Originalbilder**. Es wird höchstens eine Abfrage versucht; Fehler,
fehlende Berechtigung und Rate-Limits werden ohne Login-Retry ausgewiesen.

Offizielle API-Dokumentation:
https://docs.cj.com/docs/productfeed-api-search

Benötigte **vorhandene oder eigenständig eingerichtete autorisierte**
serverseitige Parameter (nicht in Git committen):
- \`CJ_PRODUCT_FEED_TOKEN\`: CJ Developer Personal Access Token
- \`CJ_PUBLISHER_COMPANY_ID\`: eigene CJ Company ID
- \`CJ_NOTINO_ADVERTISER_COMPANY_ID\`: tatsächlich im CJ-Konto bestätigte
  Advertiser Company ID des Notino-Programms; **nicht** aus einer vorhandenen
  \`click-<publisher>-<adid>\`-Tracking-URL ableiten.

Beispiel (ohne zusätzliche Abos und ohne Produktveröffentlichung):

\`\`\`bash
python -m scripts.check_dufynd_cj_notino_feed \
  --output /tmp/dufynd-cj-notino-feed-inventory.json
\`\`\`

Ist kein gültiger vorhandener Satz an Zugangsdaten verfügbar, endet die Prüfung
ohne Netzwerkanfrage und mit klarem Konfigurationsblocker. Eine erfolgreiche
Feed-Inventarabfrage beweist **weder** aktives Affiliate-Programm,
**noch** exakten EAN/Größen/Konzentrationsmatch, frischen SKU-Preis, verifizierten
Bestand oder Versandkosten, noch Bildrechte. Der Probe-Report kann daher keine
\`verified\`-Snapshots erstellen, keinen 72h-Timer verlängern und keine
bestehende Notino-Freigabe ändern. Solche Daten werden erst nach einem
separaten qualifizierten Product-Detail- und Rechte-Gate in den vorhandenen
\`prepare_dufynd_runtime_offer_batch.py\` übernommen. Es wurde **keine**
produktive Supabase-Tabelle oder GitHub-Workflow-Aktivierung erzeugt.

**Awin-Grenze:** Der vorhandene Top-Parfümerie-Feed 91379
ist ein offizieller Bild-/Produkt-Review-Weg, aber die archivierte
Feed-Metadatenquelle hatte keine zuverlässig befüllten EAN-, Versand- und
Bestandsfelder. Außerdem liegen zurzeit keine kanonischen Top-Parfümerie-
Kaufangebote mit freigegebener Affiliate-Route vor. Deshalb weder aus einem
frischen CSV-Download noch aus dessen Abrufzeitpunkt eine
Kaufangebots-Verifizierung ableiten. Die vorhandene
\`fetch_dufynd_awin_data_feed.py\` und Bild-Review-Skripte bleiben
unverändert – keine zusätzlichen Download-Schleifen.

**Perfumetrader:** Awin-Produktfeed im vorhandenen Provider-Config
\`dufynd_awin_perfumetrader_provider_config.json\` als nicht verfügbar
gekennzeichnet. Keine erneuten erfolglosen Anmeldungen oder Feed-Resets.


## Schreibprüfung & CJ-Inventar (24.10. · nur Entwicklungsbranch)

Der Preisbatch bestätigt \`APPLIED\` jetzt erst nach einem separaten
**ungecacheten** Supabase-Readback aller gespeicherten Angebote. Pro Eintrag
werden Offer-/Produkt-/Händler-/SKU-Fingerprint, Währung, Versand,
Preis, Bestand, Quelltyp, Evidenzhash, ursprüngliche Verifikationszeit und
HOLD-Status exakt verglichen. Der Aufruf verwendet denselben bestehenden
privaten Servicezugang; keine neue Infrastruktur, kein Händler-Clickout.
Ein erfolgreicher HTTP-Upsert mit abweichender Rücklese gilt als
\`offer_batch_write_state_unconfirmed_check_audit_no_retry\`:
Der Datenbank-Commit *kann bereits erfolgt sein*; daher Audit prüfen und
**nicht automatisch denselben Batch wiederholen**.

Die CJ-Suche prüft nun \`count\`, \`totalCount\` und \`resultList\`
gegeneinander. Eine unvollständige Liste darf nicht als \`NO_FEED\`
interpretiert werden. Einzelne Feed-Treffer werden ausdrücklich als
\`publisher_partnership_verified=false\` markiert, weil die offizielle
CJ Product Feed Summary auch nicht beigetretene Advertiser enthalten kann
(Quelle: https://docs.cj.com/docs/productfeed-api-search). Auch eine
frische Feed-Metadatenuhr ist **kein** SKU-Preis-/Bestandsbeweis.


## Kein doppeltes Produkt-Onboarding (24.10., DEV-only)

Der Default-Reviewbatch lässt bereits öffentlich vorhandene \`product_id\`s
jetzt aus und wählt die ersten **10–20 unveröffentlichten** Staging-Düfte.
Explizite \`--product-ids-file\`-Audits dürfen weiterhin bekannte
öffentliche Produkte prüfen, ohne diese erneut zu publizieren.
Die Ausgabe dokumentiert \`staged_already_public_count\`,
\`unpublished_staging_backlog\` und
\`default_selection_excludes_public\`, um doppelte Review-Arbeit sichtbar
zu machen. Der Repository-Snapshot vom 24.10. enthält **50** Staging-Düfte,
davon **5 bereits öffentliche** und **45 unveröffentlichte Profile**.
Die ersten 20 noch unveröffentlichten Profile haben derzeit **keine
registrierte originale Packshot-Freigabe**. Das ist ein
Bildrechte-/Quellenblocker, keine API-Störung oder Freigabe zur
synthetischen Flakon-Erstellung.


## 24.10.2026 – Unveröffentlichte Düfte: vorhandenen Awin-Bildprüfer wiederverwenden

**Eine neue Bildtechnik wurde ausdrücklich nicht gebaut.**
\`scripts/report_dufynd_unpublished_photo_sources.py\` nutzt denselben
\`build_commerce_wave\`-Review mit automatisch ausgeschlossenen öffentlichen
Duftprofilen und übergibt bei *tatsächlich vorhandener aktueller offizieller*
Top-Parfümerie-Feeddatei die unveröffentlichten Lücken an die **bereits
bewährte** \`report_dufynd_public_photo_feed_leads.create_review\`-Prüfung.

Ein sinnvoller kostenloser, **rein lesender** Start funktioniert sofort,
auch ohne aktuelle Feed-Credentials:

\`\`\`sh
python scripts/report_dufynd_unpublished_photo_sources.py \
  --batch-size 20 --output /tmp/dufynd-unpublished-source-queue.json
\`\`\`

Der Report identifiziert Händler-Mappings, bereits gespeicherte
Affiliate-Routen, fehlende registrierte Bilder, widersprüchliche EANs,
Source-Pfade und explizite Review-Prioritäten, ohne Preise, Belege,
Originalbilder oder Permission-Flags zu ändern. Ein vorhandener Tracking-Link
wie bei Lattafa Eclaire begründet eine **Priorität zur manuellen Prüfung**,
keine neue Freigabe oder Aussage über seinen aktuellen Zustand.

Nur **nach** einem bereits autorisierten, offiziellen Awin-Feeddownload
(durch die bestehende, getrennt freigegebene
\`dufynd-awin-feed-revalidation.yml\`, nicht hier ausgelöst):

\`\`\`sh
python scripts/report_dufynd_unpublished_photo_sources.py \
  --batch-size 20 \
  --feed /secure/read-only/top-parfuemerie.csv \
  --feed-metadata /secure/read-only/awin-feed-metadata.json \
  --output /tmp/dufynd-unpublished-photo-review.json
\`\`\`

Fehlen Downloadbeleg, Aktualität (max. 7 Tage), Advertiser 31081/Feed
91379, bestätigter Beitritt, bestehender Rechtsnachweis, genaue
Duftidentität, SKU-Eindeutigkeit oder sichere Bild-URL, darf daraus
**keine** Bildfreigabe entstehen. Name-only-Treffer bleiben menschliche
Mapping-Recherche, nie SKU-/EAN- oder Lizenzfreigaben. Alle Kandidaten
bleiben \`registered=false\`, \`published=false\`, und es gibt null
automatische Medienaktivierungen.

**Aktueller exakter Repository-Befund** (noch keine neuen Quellen):
50 Staging-Profile, davon 5 bereits öffentlich und 45 unveröffentlicht.
Die ersten 20 unveröffentlichten Düfte besitzen null registrierte,
freigegebene Originalbilder. Drei davon haben eine aufgezeichnete
Notino-Mapping-Zuordnung, aber **keine davon** den Status
\`verified_current_variant\` für Notino. Die fünf Top-Parfümerie-Mappings
des Gesamtbestands beziehen sich auf bereits öffentliche Produkte, nicht
auf diese 20; Kandidaten sind daher nur durch frische, vollständig
nachkontrollierte Namens-/Duftvariantenrecherche möglich.


## Aktuelle Feed-Version statt erneuerter Download-Uhr (24.10., Sicherheitsgate)

Die unveröffentlichten 20er-Bild-Reviews benötigen jetzt die **exakt
heruntergeladene offizielle Awin-Datei** und prüfen zusätzlich zum bestehenden
Partner-/Rechte-/SKU-Gate:

- \`download_sha256\` und \`downloaded_bytes\` der tatsächlich geladenen
  CSV-Datei gegen die Metadaten des bestehenden Awin-Feed-List-Downloads.
- Offizielle Awin-Download-Domain; niemals einen beliebigen lokalen
  Upload als bewiesene Händlerquelle behandeln.
- Das Awin-Feld **Last Imported** muss eine plausibel aktuelle
  Feed-Importversion enthalten (maximal sieben Tage für manuelle
  Bildquellen-Sichtung). Nur eine heute erneut geladene alte Feed-Version
  gilt ausdrücklich **nicht** als aktuell.
- Awin liefert \`Last Imported\` teilweise ohne Zeitzonenangabe.
  Die zusätzliche Prüfung verwendet dann eine vorsichtige ±14-Stunden-
  Unsicherheitsmarge im siebentägigen REVIEW-Fenster; der Zeitzonenmangel
  wird ausdrücklich ausgewiesen und **kann keinen 72-Stunden-Kaufpreis
  bestätigen**.

\`scripts/fetch_dufynd_awin_data_feed.py\` zeichnet die SHA-256- und
Byte-Prüfsumme künftig nur für tatsächlich heruntergeladene Daten auf,
ohne geheime Download-URL oder API-Key ins Review-Artefakt zu schreiben.
Die bereits bestehende CI-Workflow-Datei wird **nicht automatisch**
gestartet oder geändert. Es bleibt ein Vorschlags-/Owner-Bild-Gate,
kein originaler Medienimport oder Preisupdate.

**Quellenkorrektur nach authentischer Händlerkorrespondenz:**
Top Parfümerie hat am 06.10.2026 schriftlich mitgeteilt, dass der
regelmäßig synchronisierte Awin-Feed ausschließlich lagernde Artikel
enthalten soll und seine Shop-Preise/-Bilder übernimmt. Die Nutzung von
unveränderten Bildern innerhalb einer DUFYND-Affiliate-Integration wurde
grundsätzlich befürwortet. Das ist **keine** Zusage zum dauerhaften
eigenen Bildhosting oder zur Freigabe eines bestimmten nicht erreichbaren
Originalflakons. Die gesonderte E-Mail-Anfrage zur YSL-Libre-Originaldatei
vom 22.10. bleibt vor einer selbst gehosteten Veröffentlichung offen.
Diese Händlerauskunft **ersetzt nicht** die konkrete aktuelle Feed-Datei
oder den visuellen Owner-Variantencheck.

Offizielle Awin-Dokumentation: https://help.awin.com/developers/docs/product-feed-list-download


### 24.10.2026 – Awin-FID-Provenienz und aussagekräftige Evidenz (DEV only)

Die vorhandene Awin-Feed-List liefert einen authentifizierten Eintrag für
Advertiser 31081 und Feed 91379, aber ihre **Download-URL darf nicht allein
wegen der erlaubten Host-Domain als dieselbe Feed-Version gelten**.
Der Offline-Downloader bricht vor dem Dateidownload ab, wenn das
`/fid/<ID>/`-Pfadsegment fehlt, einen anderen Feed bezeichnet oder
gleichzeitig eine abweichende bzw. doppelte `fid`-Query enthält.
Zugangsdaten im URL-Userinfo-Feld, ein anderer HTTPS-Port, Fragmente und
Kontrollzeichen werden ebenfalls abgewiesen. Gleiches gilt für HTTP-Redirects:
Sie müssen zusätzlich zum erlaubten HTTPS-Host die ursprüngliche Feed-ID
erhalten. Gesperrte URLs werden nicht als neue Belegdaten gespeichert.

Der separate geprüfte Preis-Batch benötigt jetzt auch eine **nichtleere,
begrenzte Originalbeobachtung** und eine nichtleere kontrollzeichenfreie
Quellenreferenz. Der Paket-Digest beweist dabei nur den unveränderten
eingereichten Inhalt, **keine** externe Händlerbestätigung. Historische
Metadaten, fehlende Bildrechte, Lagerbestand oder Preisfrische werden durch
diese Schutzregeln nicht nachträglich verifiziert.

Neue isolierte Regressionstestfälle decken falsche FIDs, URL-/Redirect-
Manipulationen, leere Referenzen und leere Originalbeobachtungen ab.
Alle Änderungen bleiben ausschließlich im Draft-PR #837. Neue CI-Läufe
wurden wegen ungeklärter GitHub-Actions-Kosten mit `[skip ci]` vermieden;
eine vollständige CI-/Integrations-Abnahme für diesen neuen HEAD ist
noch **offen**. Kein Awin-Login, Feedabruf, Händler-Clickout, Produktiv-
Merge, Deployment oder Supabase-Migrationslauf wurde ausgelöst.

## 24.10.2026 – Verbindliches Runtime-Händlergate und Cache-Credential-Isolation

Zusätzliche P0-Sicherheitslücke in der vorbereiteten, noch **nicht** live
aktivierten Architektur geschlossen: Offline-Import und Runtime-API benutzen
nun **dieselbe** \`approved_affiliate_route\`-Prüfung aus
\`examples/retail/api/runtime_offer_snapshots.py\` (Import-Re-Export für
bestehende Skriptaufrufer). Dynamisch freigegebene Produktangebote müssen
beim **Lesen und beim Clickout** zusätzlich gegen die veröffentlichte,
gleichrangige \`merchant_partners.json\`-Datei bestehen:

- aktive Partnerfreigabe und bei Notino exakter \`verified_product_scope\`;
- exakte Publisher-Tracking-ID im CJ-Link (historisch belegte
  \`101884613\`) beziehungsweise Awin-Publisher-ID \`3099222\` und
  zugehörige Advertiser-IDs; der Käuferzielhost muss zur
  bekannten Händlermarke passen und die Produkt-URL unverändert bleiben;
- fehlende oder fehlerhafte Partnerdatei, pausierte Partnerschaft,
  fremder Tracking-Publisher und unfreigegebene SKU: **keine** dynamische
  Kaufoffer und nicht einmal eine unnötige DB-Anfrage. Die unabhängige
  Rabanne-Purchase-Evidence für nicht umgestellte Händler bleibt unverändert.

Der private Supabase-Snapshot-Cache prüft seine URL und seine
serverseitige Schlüsselidentität **vor** der Cache-Rückgabe. Die
Cache-Isolation enthält nur einen SHA-256-Fingerprint des Schlüssels
(nicht das Geheimnis). Wird die DB-Autorisierung lokal entzogen oder
der Schlüssel rotiert, können keine früheren positiven Cache-Daten
unter der neuen Identität zurückgegeben werden. Diese Änderung ist
Teil des DEV-PRs, keine produktive Keyrotation oder Berechtigungsänderung.

Neue Regressionstests: unzulässiger Händler auch mit bestehendem
Runtime-Snapshot, fehlende Partnerdatei, pausiertes Händlerprogramm,
fremder CJ-Publisher, falscher Zielhost, API-Schlüsselrotation,
lokale Secret-Entfernung und falsches Supabase-Projekt. Noch keine
echten Quellen-/Produktfreigaben oder Angebotsupdates.


## 24.10.2026 – P0 Clickout-Readback trotz 30-Sekunden-Listen-Cache

Die letzte Kaufweiterleitung darf einen zuvor gelesenen, mittlerweile
widerrufenen Supabase-Snapshot **nicht** als Freigabe wiederverwenden.
Mit eingeschaltetem, ausdrücklich freigegebenem Runtime-Feature nutzt
die Produktliste unverändert den 30-Sekunden-Cache, während
\`MerchantOfferStore.eligible_offer\` unmittelbar vor dem Clickout eine
neue private DB-Leseanforderung mit \`Cache-Control: no-store\` fordert.
\`None\`/503, neuer \`hold\`-Datensatz und \`in_stock=false\` sperren die
Kaufweiterleitung; der Leser erhält keinen historischen Fallback. Die
neuen Live-Lesedaten aktualisieren auch den normalen Listen-Cache, sodass
ein unmittelbar darauffolgender Produktaufruf keine alte Kaufoption erhält.

Kein zusätzlicher Leseaufruf für unbekannte Angebote und keine Änderung der
legacy-nicht-dynamischen Rabanne-Zertifizierung. Die zusätzliche REST-Abfrage
erfolgt erst nach gesondertem Produktions-GO und Aktivierung des bestehenden
Runtime-Feature-Schalters auf dem vorhandenen Supabase-Service. Im DEV-CI
werden die Negativfälle \`hold\`, \`out_of_stock\` und HTTP 503 gegen einen
isolierten MockTransport geprüft; es werden keine echten Clickouts ausgelöst.


## 24.10.2026 – P0 Schutz vor überlappenden Preisreads

Ein zusätzlicher Parallelitätsfehler im neuen, noch nicht produktiven
Runtime-Cache wurde behoben: Ein langer, bereits vor einer
Clickout-Sperrprüfung gestarteter Listen-Read darf eine inzwischen
abgeschlossene, neuere DB-Prüfung (\`decision=hold\` /
\`in_stock=false\`) **nicht** nachträglich mit einem alten positiven
Cache-Snapshot überschreiben.

Jede private Datenbankabfrage erhält unter einem Lock eine monoton
wachsende lokale Anfragenummer. Beim Zurückschreiben entscheidet die
**Startreihenfolge** der Abfragen, nicht ihre zufällige Antwortreihenfolge.
Langsamere alte Antworten dürfen ihren **eigenen** bereits laufenden
Listenaufruf beantworten, aber nicht den späteren Cache oder eine neue
Kaufentscheidung wieder freigeben. Die Cache-Begrenzung auf 200 Einträge
verdrängt nur den ältesten Eintrag und verwirft nicht mehr pauschal alle
neueren Freigabe-/Sperrantworten.

Zusätzlich führt ein strukturell beschädigtes Supabase-REST-Ergebnis
(ein Nicht-Datensatz innerhalb der Liste, doppelte Offer-ID oder fremde
Offer-ID) zu einem vollständigen **Fail-closed** statt zur selektiven
Übernahme verbliebener positiver Angebote.

Tests prüfen mit tatsächlich überlappenden Mock-HTTP-Anfragen und
Synchronisationsbarrieren die alte Positive-Liste **gegen** einen neuen
HOLD sowie mehrere fehlerhafte DB-Response-Varianten. Der Runtime-Schalter
bleibt in Produktion aus; zusätzliche Kosten, DB-Migrationen und
Affiliate-Clickouts sind ausdrücklich nicht Bestandteil dieses DEV-Checks.


### Sicherheitsnachtrag – Rückgabewert laufender Käuferanfragen

Nicht nur der gemeinsame Cache, auch die Antwort an einen früher gestarteten
\`bypass_cache=True\`-Kaufvorgang folgt bei überlappenden HTTP-Requests der
neuesten abgeschlossenen Datenbankbeobachtung. Anderenfalls könnte ein
langsamer früher Clickout trotz mittlerweile erfolgreich bestätigtem
\`hold\` der zweiten Anfrage noch die alte positive Antwort erhalten.
Ein real nebenläufiger Mocktest erzwingt zwei überlappende, ungecachte
Kaufanfragen und bestätigt die Sperre **für beide** Käuferabfragen. Ein
neuer Datenbankfehler ersetzt ältere positive Antworten ebenfalls
fail-closed. Keine echten Händler-Klicks oder zusätzliche Live-Reads.

## Überlappende Käuferprüfungen · 24.10.2026 (nur DEV)

Die 30-Sekunden-Cache-ID war bisher das **vollständige Offer-ID-Tupel**.
Eine Liste mit `[A, B]` konnte deshalb eine zuvor gecachte positive
A-Beobachtung zeigen, obwohl eine spätere zwingend ungecachte Kaufprüfung
für `[A]` bereits HOLD, Ausverkauft oder HTTP 503 belegt hatte.
Die Kaufweiterleitung blieb fail-closed, aber die Listenansicht war irreführend.

Im Draft werden überlappende ID-Mengen derselben Server-Credential-Identität
nach Startgeneration verglichen. Widersprechende ältere Listen-Caches werden
invalidiert; langsame ältere Abfragen übernehmen die neueren Entscheidungen
für gemeinsam angefragte IDs, auch bei fehlgeschlagenem Backend-Read.
Unveränderte Beobachtungen erzeugen keine zusätzlichen Datenbankreads.

Regressionen prüfen [A, B] gegen späteres [A] HOLD, HTTP 503 und
Thread-Barrieren. Der Batchimport weist zudem doppelte oder ungültige
*kanonische* Offer-IDs aus der Git-Registry vollständig zurück.
**Nur Entwicklung:** kein Produktiv-Merge, kein DB-Schema, keine Runtime-
Aktivierung, keine Affiliate-Weiterleitung oder zusätzliche Kosten.


## Awin-Quellenidentität: URL-Pfad und Publisher-Schlüssel (24.10.2026, nur DEV)

Offizielle Awin-Dokumentation zum alten CSV-Feedlisten-Download:
[Product Feed List Download](https://help.awin.com/developers/docs/product-feed-list-download)
(Stand: 31.08.2026). Die Feedliste enthält eine geheime Download-URL im
Schema `https://datafeed.api.productserve.com/datafeed/download/apikey/<key>/fid/<feed-id>/...`.
Der API-Schlüssel zum **Produktfeed** ist nicht der allgemeine Awin
Partner-API-Schlüssel.

Der Offline-Downloader akzeptiert deshalb nicht nur `fid=91379` und
den erlaubten Awin-Host, sondern verlangt den kanonischen
`/datafeed/download/apikey/<key>/fid/91379/`-Pfad, den identischen
API-Schlüssel wie beim Abruf der Feedliste und eine unveränderte
Schlüssel-/Feed-ID-Kombination auf jeder HTTP-Weiterleitung.
Fremde/fehlende Schlüssel, beliebige Pfade auf Awin-Hosts oder
widersprüchliche `fid`-Parameter werden **vor** dem Feed-Download
zurückgewiesen. Fehler geben keine Schlüssel oder Downloadlinks aus.

Dies ist ausschließlich eine Legacy-CSV-Feedlisten-Regel, **keine**
pauschale Sperre anderer offizieller Awin-Schnittstellen (z. B. Enhanced
Feeds mit separater Authentisierung), die hier nicht unterstützt sind.
Getestet werden die dokumentierte URL-Form, kodierte API-Schlüssel,
andere Schlüssel bei identischer Feed-ID, Redirect-Wechsel und
nichtkanonische Pfade. Ein echter Feeddownload oder Rechte-/Preisbeleg
wurde nicht durchgeführt. Der neue Commit erfordert vor jeder
Produktionsfreigabe eine vollständige CI auf exakt diesem Entwicklungs-HEAD;
die GitHub-Actions-Abrechnung ist weiterhin nicht unabhängig als 0 €
verifiziert.


## Notino: verifizierte Produktfreigaben typfest prüfen (24.10.2026, nur DEV)

Der für `active_product_deeplink_only` verwendete
`verified_product_scope` muss eine echte Liste von SKU-Strings sein.
Ein versehentlich als String gespeicherter Wert ist in Python
substring-durchsuchbar und könnte eine eigentlich nicht freigegebene
SKU innerhalb einer längeren SKU bejahen. `null`, andere
Nichtlisten-Werte oder ungültige Listeneinträge konnten außerdem
Ausnahmen statt einer sauberen Sperre verursachen.

Der gemeinsame, unveränderte Affiliate-Routenprüfer lehnt solche
fehlerhaft formatierten Freigaben jetzt **fail-closed** ab.
Regressionen decken ungültige Scope-Typen, Teilstrings und einen
korrekten exakten Listen-Scope sowohl für die Affiliate-Prüfung als auch
für den Offline-Preisbatch ab. Bestehende Partnerrechte, bestätigte
Einzel-SKU-Scopes, Trackinglinks und kaufbare Live-Angebote werden
dadurch **nicht** automatisch erweitert oder aktiviert.

## 24.10.2026 – Weiteres DEV-Hardening: Tracking-Query-Shadowing & Feedlisten-Redirects

- **Runtime-/Batch-Affiliate-Sicherheitsgate** in `examples/retail/api/runtime_offer_snapshots.py`: Fallvarianten-Duplikate von Query-Schlüsseln sind jetzt auch über Groß-/Kleinschreibung hinweg verboten. Sonst konnte z. B. ein `URL` zusätzlich zu `url` oder `AWINMID` zusätzlich zu `awinmid` die eindeutige Händler-/Publisher-Zuordnung unterlaufen. CR/LF/TAB und führende/trailing Leerzeichen in Affiliate- und Ziel-URLs werden vor der URL-Normalisierung gesperrt. Bereits freigegebene kanonische CJ-/Awin-Routen behalten ihr Format.
- **Awin-Feedlisten-Redirect** in `scripts/fetch_dufynd_awin_data_feed.py`: Der private Feedlisten-Leseweg bindet erlaubte Host-Redirects zusätzlich an exakt denselben Awin-Publisher-Schlüssel und Listenpfad. Fremde API-Schlüssel, ein Feed-Download statt der Liste oder querybasierte Schlüssel-/Feed-Overrides führen zu einer geheimnisfreien Sperrmeldung.
- **Regressionstests**: reale kanonische Notino- und Perfumetrader-Testdatensätze mit zusätzlichen URL-/AWINMID-/AWINAFFID-/UED-/CLICKREF-Schattenparametern, URL-Kontrollzeichen und Awin-Listenumleitungen; erlaubte unveränderte Listenweiterleitungen sind enthalten.
- **Abnahmegrenze:** Nur Entwicklung, keine Live-Awin-Abfrage und kein Affiliate-Clickout. Weil die GitHub-Actions-Abrechnung noch nicht unabhängig als 0 € bestätigt ist, darf ein hier ausgeführter Commit **nicht** als vollständiger CI-Erfolg gelten. Vor Freigabe echte Repository-Pytests und vollständige exakte-HEAD-CI, anschließend separater Owner-Release-GO. Händlerpreise, Lieferbarkeit und Bildrechte bleiben unbestätigt.

### Ergänzung – Released-offer-Integrität beim Lesen

Der Käufer-API-Reader `MerchantOfferStore._load` gibt bei unlesbaren, strukturell beschädigten oder doppelt adressierbaren `offer_id`-Einträgen keine Teilmenge frei und versucht keine private Runtime-Abfrage. Die Prüfung findet **vor** der Filterung nach Produkt/Offer statt, damit zwei kanonische Zeilen denselben `/api/clickout/<offer_id>`-Pfad nicht unterschiedlich interpretieren. Regressionstests decken defekte JSON-Form, falsche Datentypen und mehrfach vorhandene Kennungen in aktivierter wie deaktivierter Snapshot-Betriebsart ab. Kein Produkt wird dadurch hinzugefügt oder freigegeben. Vollständige exakte-HEAD-CI weiterhin **nicht gelaufen**.
