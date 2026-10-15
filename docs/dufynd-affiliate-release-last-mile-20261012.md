# DUFYND Affiliate Last Mile — 12.10.2026

**Entscheidung: kein neuer öffentlicher Release.** Die bestehende Perfumetrader-Strecke ist technisch vorbereitet und die genaue Variante aktuell kaufbar. Der engste offene Nachweis ist der unabhängige Awin-Reportingzugriff, einschließlich Netzwerkbeleg und aktueller Transaktionen/Provisionen. Ein fehlender Verkauf ist keine technische Sperre; fehlender Messzugriff bleibt hier eine offene Release-Voraussetzung.

## Tatsächlich aktualisierte Händlerbelege

Direkte, ungetrackte HTTPS-GETs am 12.10. um 10:01 Uhr Berlin. Keine Warenkorbaktion, keine Affiliate-Redirect-Probe, keine Testbestellung. Quellen-URLs, Beobachtungszeiten und HTML-SHA256 stehen in `examples/retail/data/dufynd_affiliate_release_last_mile_20261012.json`.

| Händler / exakte Variante | SKU | Preis | Kaufbarkeitsbeleg | Erste ungetrackte Landing-Auswahl |
|---|---|---:|---|---|
| Perfumetrader / 1 Million EDT 100 ml | 16978322 | 71,90 € | InStock; Seite nennt 2 Stück | exakt 100 ml |
| top / Bois Impérial EDP 100 ml | 924719 | 91,95 € | salable + stockState; 21 Stück, davon 18 sofort bereit | exakt 100 ml |
| top / 1 Million EDT 100 ml | 707368 | 102,95 € | salable + stockState; 1 Stück, davon 0 sofort bereit | **50 ml — HOLD** |
| top / Stronger With You Intensely EDP 100 ml | 849484 | 107,95 € | salable + stockState; 3 Stück, davon 1 sofort bereit | **30 ml — HOLD** |
| top / Layton EDP 125 ml | 812773 | 290,00 € | salable + stockState; 3 Stück, davon 1 sofort bereit | **75 ml — HOLD** |
| top / Uomo Born in Roma Intense EDP 100 ml | 897029 | 129,95 € | salable + stockState; 3 Stück, davon 1 sofort bereit | **50 ml — HOLD** |

Die top-Preise wurden über Größenoption → interne Varianten-ID → SKU → `optionPrices.finalPrice` verbunden. Kaufbarkeit folgt der gleichen Varianten-ID in `salable` und `jsonSwatchConfig`; sie ist eine Händlerangabe, keine Checkout-Bestätigung. Insbesondere ist Rabanne bei top nicht als sofort versandfertig nachgewiesen. Ein optionales Händler-Geschenk macht das ausgewählte Einzelprodukt nicht automatisch zu einem Größenkombinationsset.

Perfumetrader: aktuelle Seite bestätigt GTIN **3349666007921**, SKU, EDT und 100 ml. Deutsche Standardzustellung kostet weiterhin 4,99 €; Gesamtpreis **76,89 €**. Kein Bestpreisversprechen. Bestehende Publisher-ID **3099222**, Advertiser **11672** und erfolgreiche exakte Redirect-Kette vom 10.10. werden übernommen (`ops.first_money_affiliate_truth_20261010`). Kein erneuter Klick. Die zertifizierte Laufzeit-Frische vom 10.10., 19:56 UTC ist zum Prüfzeitpunkt gültig und läuft ohne erneute reguläre Verifikation am **13.10., 19:56 UTC** aus; sie wurde hier nicht verändert.

## top Parfümerie: geschlossen und weiterhin offen

Neu geschlossen: fünf aktuelle, exakt zugeordnete Preis-/Kaufbarkeitsbelege; Bois Impérial als exakte erste Landing-Auswahl; alle fünf bereits geprüften Bilddateinamen gehören weiterhin zur jeweiligen Händler-Variantengalerie. Fotos, visuelle Freigaben und Dateihashes wurden übernommen, nicht erneut erzeugt oder freigegeben.

HOLD: Für diese fünf SKUs fehlen aktuelle sichere, an Publisher 3099222 und Advertiser 31081 gebundene Affiliate-Links sowie deren bereits vorhandener unabhängiger Tracking-/Netzwerkbeleg. Vier generische Landingpages wählen zunächst eine andere Größe. Ein bekannter erfolgreicher Redirect für andere top-SKUs ist kein Beweis für diese fünf Produkte. Keine erfundenen Größenparameter und keine Übernahme fremder Trackingfreigaben.

Der manuelle Awin-Workflow bleibt laut aktuellem Auftrag und gespeichertem technischen Befund gesperrt. Der erlaubte Empfängerrotationspfad betrifft ausschließlich `scentai-mvp`; dieser Branch darf hier nicht verändert werden. Ein lesender Versuch, die Workflow-Laufliste über den Connector zu aktualisieren, wurde von dessen URL-Allowlist abgelehnt. Kein weiterer Versuch, kein alternativer Zugriff, keine Triggeränderung und kein Secret-Zugriff. Das vorhandene bereinigte Fotoartefakt enthält keine zur Aktivierung geeigneten Tracking-URLs.

Die schriftliche top-Bestätigung (`affiliate.evidence.top_parfuemerie.20261006`) und Rechtebasis `awin_top_parfuemerie_feed_materials_20260928` gelten im DUFYND-Affiliate-Publisher-Kontext für top. Der vorbereitete Platzierungsvertrag bindet jede exakte SKU an ihren unveränderten Bildhash, top als beworbenen Händler und dessen exaktes Kaufziel. Keine Verwendung dieses Rabanne-Fotos in einer reinen Perfumetrader-Strecke. Öffentliche Platzierung, Registereintrag und Release bleiben gesondert gesperrt; die fünf visuellen Owner-Freigaben werden nicht erneut angefragt. Althaïr bleibt unverändert HOLD.

## First-Money-Messung

Bestehendes `scripts/report_dufynd_profitable_growth.py` auf den vollständig gezählten 32 Zeilen der Service-Ansicht angewendet; keine neue Messpipeline. Zeitraum 05.10., 05:20 UTC bis 12.10., 08:00:59 UTC:

| Klasse | Ereignisse | Sessions | Händler-Clickouts |
|---|---:|---:|---:|
| Interne QA | 104 | 20 | 13 |
| Unklassifiziert | 98 | 42 | 4 |
| Als Besucher klassifiziert | 32 | 11 | 1 |

Eine TikTok-Strecke erfüllt technisch Landing → Produktinteresse → Clickout. Sie kann der bekannte Owner-Test vom 11.10. sein und ist **kein unabhängig bestätigter Kundenerfolg**. Kein ausreichendes Sample. Seit dem vorherigen Delta-Checkpoint um 06:49:07 UTC keine neuen Ereignisse. Ein Besuchersignal und ein qualifizierter Ablauf sind keine Netzwerktransaktion.

Die aktuelle Connector-Abfrage liefert nur Instagram, TikTok und YouTube, keine verbundenen Awin-/CJ-Reportingkonten. Netzwerktransaktionen und bestätigte Provisionen im aktuellen Zeitraum bleiben **unbekannt / null**. Der alte Owner-Bericht mit null Transaktionen vom 01.–04.10. gilt ausschließlich für dessen damaliges Zeitfenster.

## Konkreter nächster Nachweis und spätere Owner-Entscheidung

Zuerst ein autorisierter **originaler Awin-Transaktions-/Provisionsbericht** für Publisher 3099222 / Perfumetrader 11672, 01.–12.10., alle Status, mit Zeitraum/Zeitzone, Transaktions-ID/-Datum, ClickRef1–6, Betrag/Währung und Provision/Status. Bereits vorhandene QA-Referenz vom 10.10. nur für einen Netzwerkabgleich verwenden, niemals als Kundenumsatz; keinen neuen Probe-Click erzeugen. Keine Zugangsdaten im Chat. Ein leerer Bericht belegt ausschließlich die Abwesenheit von Transaktionen in seinem ausgewiesenen Zeitraum und ersetzt keinen Klickempfangsbeleg.

Erst nach Schließen dieser Nachweise: gesondertes GO für den konkret geprüften PR-Commit, öffentliche Platzierung und Release/Deploy; Angebotsaktivierung nur, falls ausdrücklich Bestandteil dieses GO. Derzeit **keine vollständig freigegebene neue Produktstrecke** und keine automatische Aktivierung.

## Gezielte technische Korrektur

Der vorhandene Adaptercheck meldete für die echte Perfumetrader-Konfiguration fälschlich `READY_FOR_FEED_PREFLIGHT`, obwohl `awin_product_data_available=false`. Er meldet jetzt `WAITING_DIRECT_MERCHANT_EVIDENCE` und verweist auf direkte exakte Händlerbelege und vorhandene Affiliate-Nachweise. Dies ist keine Produktfreigabe. Bestehende Programm-/Vertragsgates haben weiterhin Vorrang; verfügbare Feeds behalten ihren bisherigen Ablauf. Drei Regressionstests ergänzt, keine bestehenden Tests abgeschwächt.

Produktionsangebote, Bildregister, Fotos, Layouts, geschützter Awin-Workflow, `main`, `scentai-mvp`, PR #775 und Social-Posts unverändert. Keine zusätzlichen Kosten, Händlerkontakte, Käufe, Merge oder Veröffentlichung.
