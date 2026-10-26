# Sechs exakte Top-Parfümerie-Angebote – vorbereitet, nicht veröffentlicht

Der aktuelle offizielle [Awin-Lauf 40324201008](https://github.com/tncommerce/commerce-agents/actions/runs/40324201008)
bestätigt am 26.10.2026 um 12:39:33 UTC die aktive Mitgliedschaft für
Advertiser 31081 / Feed 91379. Die sechs Original-`pclick.php`-Links bleiben
unverändert. Der vollständige Feed wurde weder veröffentlicht noch gespeichert.

Danach wurden alle sechs Größen im echten Chrome auf den direkten Händlerseiten
ausgewählt: SKU, Preis, Lieferbarkeit und sichtbarer aktivierter Kaufbutton
stimmen überein. Kein Warenkorb und kein Affiliate-Clickout wurde ausgelöst.
Die eigene Versandseite bestätigt um 12:48:56 UTC kostenfreien Versand nach
Deutschland ab 49,95 EUR. Die nachstehenden Gesamtpreise enthalten daher 0 EUR Versand.

| Produkt | SKU | Variante | Gesamtpreis | Händlerauswahl |
|---|---|---|---:|---|
| Bois Impérial | 924719 | EDP 100 ml | 91,95 EUR | öffnet direkt 100 ml |
| Rabanne 1 Million | 707368 | EDT 100 ml | 102,95 EUR | 100 ml auswählen |
| Stronger With You Intensely | 849484 | EDP 100 ml | 107,95 EUR | 100 ml auswählen |
| Layton | 812773 | EDP 125 ml | 290,00 EUR | 125 ml auswählen |
| Uomo Born In Roma Intense | 897029 | EDP 100 ml | 129,95 EUR | 100 ml auswählen |
| Althaïr | 904707 | EDP 125 ml | 290,00 EUR | 125 ml auswählen |

Die fünf Auswahlhinweise stehen ausdrücklich im vorhandenen `variant_label`,
das die öffentliche API ausgibt und `FragranceOffers` oberhalb des Kaufbuttons
anzeigt. Kein erfundener Größenparameter und keine Behauptung, der Original-Link
öffne bereits diese fünf Größen. Das günstigere Perfumetrader-Rabanne-Angebot
wird nicht verändert und gewinnt weiterhin bei niedrigerem bestätigtem Gesamtpreis.

GTINs stammen aus den jeweils benannten historischen exakten Varianten- bzw.
Händlergaleriebelegen; der neue Feed enthält kein GTIN-Feld. Seine Downloadzeit
wird nicht als neue Preisprüfung ausgegeben. Maßgeblich sind die sechs echten
Browserzeiten zwischen 12:41:59 und 12:43:32 UTC.

## Prüfnachweis

`dry-run.json` enthält sechs mit dem bestehenden Importer vorbereitete Datensätze.
Dabei werden ausschließlich die vorgeschlagenen Konfigurationen im Speicher
verwendet. **Keine produktive Partner-, Angebots-, Mapping- oder Datenbankdatei
wurde geändert.** Das normale Importkommando akzeptiert diese neuen Angebote
vor einer ausdrücklich freigegebenen kanonischen Einführung absichtlich nicht.

```bash
python artifacts/dufynd-top-six-offers-20261026/prepare-reviewed-batch.py
python -m pytest -q tests/test_dufynd_top_six_offer_candidates.py
```

13 gezielte Offline-Tests bestanden. Sie prüfen die Originalbelege, unveränderte
Links, sechs Kundenpayloads, fünf Auswahlhinweise, falsche Publisher/Produkte,
fehlende SKU, doppelte Bindungen, Ablauf und den bestehenden Rabanne-Vorrang.
Dies ist keine vollständige CI und kein ausgeführter Affiliate-Klicktest.

Batch: `top-six-20261026T124332Z`.
SHA256: `c66f2cd026f83073f12d1985a1b9f770ab71d4aebfd45f6f2ac680c7e9cce718`.
Alle sechs gemeinsam gültig bis **29.10.2026 12:41:59.016 UTC**; danach braucht
mindestens der früheste Beleg eine neue echte Händlerprüfung.

## Begrenzte spätere Einführung nach GO

`proposed-offers.json`, `proposed-partner.json` und `proposed-mappings.json`
bezeichnen genau die sechs vorgeschlagenen Ergänzungen. Bestehende andere
Händlerangebote und Freigaben müssen beim Übernehmen erhalten bleiben.
Die schmale `pclick.php`-Erweiterung akzeptiert nur explizit freigegebene
Top-Produkt-SKUs mit passender Feed-, Awin-Produkt-, Publisher- und Zielbindung.
Sie aktiviert für sich allein nichts. Ein späterer Runtime-Import setzt den
gesondert freigegebenen Runtime-Rollout und die passende Händlerscope voraus.

Vor produktivem Import die sechs echten Vorherzustände sichern; Rücknahme nur
dieser sechs unverändert gebliebenen Batch-Zeilen bzw. Konfigurationsdeltas.
Neuere Händlerbelege niemals überschreiben. Die hier verwendeten Bildrechte
gelten für die DUFYND-Platzierung zugunsten von Top Parfümerie; sie erteilen
keine allgemeine Nutzungserlaubnis für Werbung ausschließlich anderer Händler.
