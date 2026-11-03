# DUFYND: 10 Top-Angebote – Preisfrische und Käuferwert

**Quellenstand 27.10.2026 · sichere Nur-Lese-Priorisierung, keine neuen Preis-/Bestandsnachweise.** Das exakte Release auf `36cc84c` hat Browser-QA [#40492433775](https://github.com/tncommerce/commerce-agents/actions/runs/40492433775) bestanden: **zehn** echte Top-Kaufangebote sind im mobilen Browser sichtbar, und **zehn** andere, aber teilweise überlappende Originalbilder laden korrekt. Dies bestätigt den UI-Kaufweg, nicht die Abrechnung einer Affiliate-Provision.

## Echte Ablaufzeiten (Deutschland, 29.10.)

| Produkt | Top-Gesamtpreis aus 26.10-Quelle | 72h-Ablauf, Berlin | Andere Händler: historische Recherche, keine heutigen Preise |
| --- | ---: | --- | --- |
| Essential Parfums Bois Impérial | 91.95 € | 29.10., 13:41 | Douglas: 94.00 € (**30.8 Tage alt; nicht aktuell**) |
| Rabanne 1 Million | 102.95 € | 29.10., 13:42 | Müller: 67.95 € (**29.6 Tage alt; nicht aktuell**) |
| Giorgio Armani Stronger With You Intensely | 107.95 € | 29.10., 13:42 | Douglas: 79.99 € (**30.9 Tage alt; nicht aktuell**) |
| Parfums de Marly Layton | 290.00 € | 29.10., 13:42 | Kein Preisvergleich im Bestand |
| Valentino Uomo Born In Roma Intense | 129.95 € | 29.10., 13:43 | Douglas: 119.00 € (**30.8 Tage alt; nicht aktuell**) |
| Parfums de Marly Althaïr | 290.00 € | 29.10., 13:43 | Kein Preisvergleich im Bestand |
| Montblanc Explorer | 113.00 € | 29.10., 16:16 | Douglas: 79.99 € (**30.8 Tage alt; nicht aktuell**) |
| Creed Aventus | 354.00 € | 29.10., 16:16 | Kein Preisvergleich im Bestand |
| Prada L'Homme | 117.95 € | 29.10., 16:18 | Douglas: 109.99 € (**30.8 Tage alt; nicht aktuell**) |
| Xerjoff Naxos | 242.00 € | 29.10., 16:19 | Parfum-Zentrum: 170.71 € (**30.8 Tage alt; nicht aktuell**) |

**Achtung:** Ein Magento-Live-Signal vom 27.10. bestätigte für Rabanne und Montblanc die 100-ml-`optionPrices` im Shop-Konfigurator (102,95 € bzw. 113,00 €); es konnte aber weder Awin-Händler-SKU auf Magento-intern-ID noch stock/aktuelle Versandwahl im Warenkorb vollständig verketten. **Das erneuert keine dieser Zeiten.** Siehe [separater Nachweis](./top-two-official-option-price-signals.json). Sämtliche alternativen Vergleichspreise in obiger Tabelle sind rund einen Monat alt; sie dürfen weder als aktuelle Käuferoption noch als aktuelle Preisführerschaft beworben werden.

## Geschäftliche Reihenfolge

1. **Rabanne 1 Million EDT 100 ml:** Der unabhängig durch Supabase neu zertifizierte **Perfumetrader 76,89 € inkl. Versand** ist preislich vor Top 102,95 €; DUFYND setzt ihn korrekt auf Platz 1. Der Nachweis stammt vom 26.10. um 14:28 UTC und hat ebenfalls eine 72h-Grenze.
2. **Bois Impérial EDP 100 ml:** Top 91,95 € liegt zwar unter einer einmonatigen Douglas-Referenz von 94 €, aber ohne aktuellen Gegenpreis keine aktuelle Bestpreisbehauptung. So lange wie gültig sachlich bewerben, keine unbelegte Rabatt-Prozentzahl.
3. **Montblanc / Naxos / Armani / Prada:** Die alten Fremdvergleichswerte sind in mehreren Fällen niedriger als Top; dringend die **aktuell** kaufbaren Gesamtpreise und Netzwerkberechtigung anderer Partner recherchieren, bevor wertvolle Käufer auf einen mutmaßlich teuren Händler geführt werden.
4. **Layton / Althaïr / Aventus:** Keine belastbare aktuelle Vergleichsbasis im vorhandenen Datenbestand; fehlende Konkurrenz ist **kein** Bestpreisbeweis.

## Harte Regel am 29. Oktober

**Keine bloße Umdatierung** der Top-Angebote. Exakte Zielvariante (SKU, EAN, Konzentration, ml), reale Lagerfähigkeit und DE-Endsumme müssen in einer frischen offiziellen Quelle zusammenpassen. Ohne Nachweis wird das jeweilige Angebot nach 72h korrekt ausgeblendet. Keine Affiliate-Clickouts, keine manuellen Testkäufe, keine Render-Neubuilds allein zur Datumsverlängerung, kein SQL-Snapshot oder Feature-Flag ohne Freigabe.

Der Stand ist ein priorisierter **Commerce-Handoff**, nicht der Nachweis neuer Käufer/Sales. Vollständige Zeilen ohne Trackingziel stehen in [offer-freshness-watchlist.json](./offer-freshness-watchlist.json). 0 € zusätzliche Ausgaben.
