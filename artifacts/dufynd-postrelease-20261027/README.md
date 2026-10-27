# DUFYND · Händler-Varianten und Preisfrische – 27.10.2026

Nach erfolgreich abgeschlossenem P0-Release wurden **zwei offizielle, nicht getrackte Händlerproduktseiten** am **27.10. um 11:41 UTC** direkt read-only geprüft: [GitHub-Originalquelle #40498052180](https://github.com/tncommerce/commerce-agents/actions/runs/40498052180). Beide Produktseiten antworteten HTTP 200, enthielten die erwarteten Awin-Feed-SKUs und historischen EANs im HTML und lieferten Magento-`optionPrices` je Größe.

| DUFYND-Produkt | Awin-SKU | 100-ml-Preisindikator aus Händler-Konfiguration | Getrennte interne Varianten |
| --- | --- | ---: | --- |
| Rabanne 1 Million **EDT 100 ml** | 707368 | **102,95 €** | 50/100/200 ml, Magento-IDs 15570/15571/15572 |
| Montblanc Explorer **EDP 100 ml** | 849457 | **113,00 €** | 30/60/100 ml, Magento-IDs 10338/10339/10340 |

**Beide Preisindikatoren stimmen mit den bereits freigegebenen alten Angebotssummen überein.** Das beweist nicht automatisch eine noch verfügbare 100-ml-Variante oder dass die Magento-interne numerische Varianten-ID mit der Awin-Händler-SKU identisch ist – sie sind tatsächlich **verschieden**. Die offizielle Seite bietet eine Größen-Auswahl; ohne Auswahlbestätigung, konkrete Lagerverfügbarkeit und Warenkorb-/Versandgesamtpreis **keine neue 72-Stunden-Zertifizierung**.

Ein unzulässiger Zeitstempel-Refresh würde in knapp zwei Tagen eventuell falsche oder nicht bestellbare Angebote sichtbar halten. Deshalb sind alle Source-Proben ausdrücklich **REVIEW_ONLY**. Keine Affiliate-Links geöffnet, kein Preis verändert, keine Produktbilder geändert, kein Render-Deploy oder DB-Schreibzugriff. Die reguläre 72h-Sperre muss am **29.10. ca. 13:41–16:19 Berlin** unverifizierte Angebote selbst ausblenden. Rabanne-Perfumetrader ist als unabhängig zertifizierter, günstigerer Kaufweg zu bewahren.

Die aus GitHub-Läufen rekonstruierten Source-Daten stehen vollständig und ohne Zugangsdaten in [top-two-official-option-price-signals.json](./top-two-official-option-price-signals.json). **Nicht** die ausgewiesenen Größen als neue verfügbare Offers aktivieren: Next step ist eine EAN/SKU→Magento-intern-ID-Bindung **plus** tatsächliche ausgewählte Größe, Bestand und finaler DE-Gesamtpreis in derselben frischen Quelle. Nach Befund der Struktur keine 10-fache Wiederholung bloßer HTTP-GETs ohne weitere Identitätsprüfung.

## Release-/Quellgrenzen

Das bestehende Commerce-Draft [PR #837](https://github.com/tncommerce/commerce-agents/pull/837) bleibt DEVELOPMENT ONLY. Der im Produktion-HEAD `36cc84c` erfolgreich freigegebene Bild-/Angebotsrelease wird durch diese reine Quellnotiz **nicht** verändert. Die zehn Top-Angebote sind heute mit Browser-QA #40492433775 belegterweise noch sichtbar. Die originalen Awin-Produktdeeplinks sind nach wie vor nur in den kanonischen Commerce-Dateien, nie in den öffentlichen Recherchen als konstruiertes Trackingziel.
