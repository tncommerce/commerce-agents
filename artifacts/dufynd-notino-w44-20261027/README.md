# DUFYND · Notino/CJ Week 44 – Quellkampagne, keine Gutschein-Aktivierung

**Beobachtung: 27.10.2026. Status: REVIEW_ONLY / nicht live.** Die originale CJ-Advertiser-Mail von Notino vom 23.10.2026 bestätigt Deutschland-Kampagnen für die Kalenderwoche **26.10.–01.11.2026**. Quelltyp, Daten und Verbote sind strukturiert in [campaign-preflight.json](./campaign-preflight.json) abgelegt. Keine privaten Mail-IDs oder Tracking-Redirects dieser Mail werden in das öffentliche Repository geschrieben.

## Drei Originalaktionen (Advertiser-Mail, keine SKU-Zusage)

- `SALE` – **bis 20 %** auf **ausgewählte** Produkte.
- `BLACK` – **bis 30 %** auf **ausgewählte** Produkte (Black Friday).
- `FLASH` – **15 %** auf Bestellungen über dem deutschen Mindestbestellwert von **20,00 EUR**, **erst 30.10.–01.11.2026**. Eine individuelle Produkt-/Warenkorb-Einlösbarkeit ist nicht bestätigt.

Der Advertiser untersagt **Brand Bidding in jeglicher Match-Variante** und **Affiliate-Promotion für Hermès, Dior und Guerlain**. Ohne separate schriftliche Zustimmung keine Google-/Bing-Shopping-CSS-Anzeigen. Die Advertiser-Mail enthält *keine* bestätigte reduzierte SKU-Summe, keine tatsächliche Coupon-Einlösung und keinen Netzwerk-Provisionsnachweis. `SALE` und `BLACK` haben bei einzelnen Produkten nur einen möglichen Maximalnachlass, **keinen** garantiert anwendbaren Rabatt.

## Prüfung gegen kanonischen Commerce-HEAD

In der freigegebenen Notino-CJ-Produkt-Scope befinden sich vier Produkte. Nur ein gespeichertes Ausgangsangebot ist bei der Prüfung vom 27.10. 07:45 Berlin jünger als die bestehende 72-Stunden-Grenze:

| Produkt | Kanonisches Angebot | Letzter echter Preisnachweis | Ausgangs-Gesamtpreis | Kampagnenfreigabe |
| --- | --- | --- | ---: | --- |
| YSL Libre EDP 90 ml, nachfüllbarer Flakon | `notino-ysl-libre-edp-90` | 26.10. 10:42:37 UTC | 130,00 EUR | **Nur Freshness der Preisbasis**, Rabatt nicht verifiziert |
| YSL Black Opium EDP 90 ml | `notino-ysl-black-opium-edp-90` | 20.10. | 116,00 EUR | Alter Preis abgelaufen |
| Parfums de Marly Delina EDP 75 ml | `notino-pdm-delina-edp-75` | 20.10. | 285,00 EUR | Alter Preis abgelaufen |
| Lattafa Eclaire EDP 100 ml | `notino-lattafa-eclaire-edp-100` | 30.09. | 37,40 EUR | Staging statt veröffentlichter Profilseite; alter Preis abgelaufen |

Diese Werte sind **historische, nicht rabattierte Datenbelege**, keine Live-Angebote aus einem neuen Browser-Checkout. Der Original-CJ-Produktlink bleibt ausschließlich in `merchant_offers.json` verankert; hier wird kein Tracking-Link generiert oder testweise geöffnet.

## Nächster zulässiger Ablauf

1. Bestehende Storefront/Backend-Endpunkte und den echten aktuellen Notino-Produktpreis nur lesend prüfen; die vorhandene YSL-90-ml-Variante nicht mit einer Refill-Flasche verwechseln.
2. Vor einer produktspezifischen Rabattbehauptung tatsächliche Einlösbarkeit im passenden Warenkorb beziehungsweise offiziellen Advertiser-Creative samt Einschränkungen belegen. `FLASH` vor dem 30.10. nicht als aktiv bewerben.
3. Händler-Code-Angebote nur mit bereits zulässigem CJ-Produktdeeplink, korrekter Affiliate-Kennzeichnung, frischem Ausgangspreis und notwendiger Release-Freigabe zeigen. Nie den billigeren, aktuelleren Rabanne-Perfumetrader-Pfad überschreiben.
4. Bei ausbleibendem Beleg **kein Preis- oder Gutschein-Claim**; unabhängig weiter an Originalbildern und echten Angeboten arbeiten.

**Technischer Effekt dieses Pakets:** reine Dokumentation/Prüfgrundlage, 0 neue Preiszeilen, 0 Affiliate-Clickouts, 0 öffentliche Bilder, 0 Produktionsänderungen, 0 EUR neue Ausgaben. Der fertig geprüfte gekoppelte Website-PR #836 und sein CI-HEAD bleiben unberührt.
