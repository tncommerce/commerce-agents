# DUFYND · Händler-/Netzwerkquellen und technische Freigaben

**Ermittelt am 24.10.2026 · für interne Prüfung · keine Live-Freigabe.**

## CJ/Notino – Authentifizierungsstand

- **CJ Publisher Company ID (CID) 8073784:** aus einer CJ-Accountänderungsbenachrichtigung vom 16.09.2026. Das ist eine vom Netzwerk stammende Kontoindikation, nicht bereits ein gültiger API-Token.
- **NOTINO.de Advertiser ID 4541231:** in einer bereits am 30.09. bzw. 20.10. versendeten DUFYND-Anfrage an das NOTINO-/VIVNetworks-Team vermerkt. Diese Kennung ist eine historische DUFYND-Aussage; erst eine originale CJ-Kontobestätigung kann ihre Eignung als Product-Feed-API-\`partnerIds\` belegen. Nicht automatisch in Live-Konfiguration eintragen.
- **CJ Personal Access Token (PAT):** in den verfügbaren autorisierten Zugängen nicht vorhanden. Die API-Abfrage \`productFeeds\` bleibt ohne PAT und unabhängig bestätigte Company IDs gesperrt; es wird kein Token aus Trackinglinks rekonstruiert. Offizielle Spezifikation: https://docs.cj.com/docs/productfeed-api-search
- **NOTINO-W44-Newsletter vom 23.10., Kampagnenzeitraum 26.10.–01.11.2026:** enthält **HERMES, DIOR, GUERLAIN** als für Affiliate-Promotion ausgeschlossene Marken und untersagt Brand-Bidding. Das ist ein W44-Kampagnenhinweis, keine generelle lebenslange Markensperre. Rabatt- oder Gutscheincodes daraus werden ohne gesonderte Berechtigung und exakte Produkt-/Provisionsabnahme nicht auf DUFYND aktiviert.

## Awin/Top Parfümerie – direkt erteilte Händlerauskunft

Schriftliche Händlerantwort vom 06.10.2026 (Betreff „DUFYND × top Parfümerie – Produktfeed / aktueller Lagerbestand“):
Der Händler erklärt, dass der offizielle Feed 91379 regelmäßig synchronisiert wird, nur tatsächlich lagernde Artikel umfasst und aktuelle Shop-Preise/-Bilder übernimmt. Die unveränderte Nutzung von offiziellen Feed-Bildern im Rahmen der DUFYND-Affiliate-Integration wird grundsätzlich befürwortet.

**Abgrenzung:** Diese Mitteilung beweist **nicht**, dass eine bestimmte historische CSV-Datei heute frisch ist, dass alle ungetesteten Varianten eindeutig zugeordnet sind, dass der Feed lückenlose EAN-/Versandfelder liefert, oder dass dauerhaftes Eigenhosting auf einer DUFYND-Domain erlaubt ist. Für genau YSL Libre EDP 90 ml, SKU 856448, EAN 3614272648425 wurde am 22.10. eine konkrete Bilddatei/Hosting-Freigabe nachgefragt. Ohne bestätigte Antwort bleibt ein eigener Originalbild-Upload gesperrt.

Offizieller Feed-List-Hinweis: https://help.awin.com/developers/docs/product-feed-list-download. Das Feld \`Last Imported\` ist Awin-Import-/Versionszeit, nicht automatisch der vom Händler per SKU gemessene Preiszeitpunkt. Der Offline-Review bindet nun Originaldatei-SHA, Dateilänge und Importfrische; **kein 72h-Angebotsrefresh** darf allein aus diesen Daten entstehen.

## Infrastruktur- und Observer-Befund

Der GitHub Actions-Lauf [#40098982847](https://github.com/tncommerce/commerce-agents/actions/runs/40098982847) vom 24.10. endete für das Produktions-Private-Observer-Read mit \`gmail_1:revoked\`. Der Fehler-Receipt-Schritt war erfolgreich; **kein Cursor wurde als gelesen bestätigt**. Das betrifft die Autorisierung des separaten Observer-Zugangs, nicht die erfolgreiche private Gmail-Connector-Lektüre in diesem Chat. Wiederherstellung verlangt berechtigte manuelle Re-Autorisierung; keine automatischen Auth-Retries.

**Supabase-Stichtag 30.10.2026:** Neue \`public\`-Tabellen sind danach nicht mehr implizit über PostgREST erreichbar. Die vorbereitete, noch nicht angewendete Migration \`20261023221100_dufynd_runtime_offer_snapshots_v1.sql\` enthält bereits explizite \`service_role\`-Tabellengrants und verweigert \`anon\`/\`authenticated\`. CI testet diese Rollen. Bei einem später separat autorisierten Rollout muss der private Data-API-Readback trotzdem live bestätigt werden. Offizielle Quelle: https://supabase.com/changelog/45329-breaking-change-tables-not-exposed-to-data-and-graphql-api-automatically

## Veröffentlichungsgrenzen

Kein neues Angebot, keine neue Provision, keine frische SKU, keine neue Bildlizenz und kein aktiver Token sind aus diesem Dossier entstanden. Architektur-PR #837 bleibt Draft. Live HEAD \`7b793cf7ce1223967e66d768fcb7930ecdfc0e40\` gewinnt. Kein Merge, DDL, Deployment, Affiliate-Klick oder kostenpflichtiger Dienst.
