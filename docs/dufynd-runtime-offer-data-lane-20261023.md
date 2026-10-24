# DUFYND · Datenbetrieb statt PR pro Händlerpreis (DEV / nicht live)

Stand: 23.10.2026. Die ersten produktiven Preisquellen bleiben **unverändert**.
Dieses Paket ist eine vorbereitete einmalige Umstellung; es ist **kein** bereits
aktivierter Notino-Feed oder eine Freigabe zur Veröffentlichung.

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
