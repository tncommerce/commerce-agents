# DUFYND · sechs zusätzliche Originalfotos · 26.10.2026

Die Bildänderungen sind im Website-Entwicklungsstand angewendet: **zehn Originalfotos statt vier, weiterhin 37 öffentliche Duftprofile**. Produktion bleibt unverändert bei vier Originalfotos. Die sechs Top-Angebote sind als konkrete private Kandidaten sichtbar; keine Affiliate-Weiterleitung oder produktive Händleraktivierung wurde ausgelöst.

| Nachgewiesener Patch | Zusätzliche Bilder | Entwicklungsbestand |
| --- | --- | --- |
| `01-five-top-parfuemerie-originals.patch` | Bois Impérial EDP 100 ml; Stronger With You Intensely EDP 100 ml; Layton EDP 125 ml; Valentino Uomo Born in Roma Intense EDP 100 ml; Althaïr EDP 125 ml mit Verpackung | 9 |
| `02-rabanne-original-after-matching-top-offer.patch` | Rabanne 1 Million EDT 100 ml, nach Patch 01 | 10 |

Die Patches bleiben als überprüfte Review- und Rücknahmeartefakte erhalten. **Nicht nochmals auf den aktuellen Entwicklungsstand anwenden.** Die lokale private Originalbildintegration wächst von fünf auf sechs Profile; Althaïr ist neu integriert. Alle sechs Dateien sind heute erneut geprüft, nicht als neue Aufnahmen ausgegeben.

## Belege und tatsächliche Prüfung

- Owner-Manifest `DUFYND_Originalbild_Quellenmanifest_20261026.json`, SHA-256 `1289fb799a55b661ad099a4faea346b6922834e1dbd8b052708d8536548fdef2`: alle sechs akzeptierten Bild-Hashes entsprechen den frisch geladenen Originaldateien. Keine Retusche, Umfärbung, KI-Flakons oder abweichende Größe.
- Aktueller offizieller Awin-Feed: Advertiser 31081, Feed 91379, aktive Mitgliedschaft; Download 26.10.2026 um 12:39:33 UTC, SHA-256 `669e9fc954c44f84d13db4aa4f0ec3f7459ff5923939bae0fda119a426fcaf5d`. [Quelllauf 40324201008](https://github.com/tncommerce/commerce-agents/actions/runs/40324201008), Job 121576555286, Source-HEAD `6a04f20f3060ef7a7a315be116a9d3c31873d3bb`.
- Sechs heutige Händler-SKU-/Größen-/Bild-Zuordnungen passen exakt zu den aktuellen Feed-Bild- und Produktseiten-URLs. GTIN, Größe, Bestand und Versand fehlen im Feed; sie werden nicht als frische Feed-Felder erfunden. Größen-/Bildidentität stammt aus konkreten Händler-Varianten, Angebotspreis/Bestand aus separater tatsächlicher Browserprüfung.
- Beide Patches wurden zuerst in isolierten Kopien angewendet, regeneriert und wieder zurückgenommen. Bildänderungen erhalten Preise, Angebote, Verfügbarkeit, Noten und Klassifizierungen. Die vier zuvor genehmigten Bildobjekte behalten ihren Inhalt und ihre Darstellung.
- Danach tatsächlicher öffentlicher Next.js-Build mit 10 Originalen/37 Produktseiten; **12 Produktseitenprüfungen bei 390/1440 px** sowie beide Katalogansichten. Armani rendert die neue Original-PNG trotz alter Cutout-Metadaten. Quelldateien sind vollständig enthalten, ohne Filter/Transform und ohne Vergrößerung über 2× Quelldichte.
- Separate tatsächliche private Website mit sechs Bild-/Angebotsprofilen: **18 Prüfungen bei 390/768/1440 px**, exakte Gesamtpreise inklusive Versand, fünf Hinweise zur erforderlichen Größenauswahl, deaktivierte Kaufbuttons. Bois benötigt keinen Größenauswahlhinweis.
- Öffentliche Render-QA verwendet lokal bereitgestellte, frisch hashgeprüfte Originalbytes. API-Anfragen sind dabei blockiert, keine Liveangebote simuliert. Private Angebotskarten stammen aus dem konkreten Commerce-Kandidatenpayload; sie haben keine Clickout-URLs, keinen API-Fetch und keine Analytics.
- **55 Prüfungen** am tatsächlichen initialen HTML-Seitenkopf. Exportprüfung plus **ein positiver und fünf negative Fälle**: fehlende Genehmigung sowie abweichender Hash, URL, Größe oder Rechtebasis werden abgewiesen. Private Routen und private Bilddateien bleiben im normalen Export ausgeschlossen. Ein konkret öffentlich genehmigtes Original darf seine zuvor private Hash-Referenz öffentlich verwenden.
- Kein vollständiger neuer GitHub-CI-Lauf für dieses Website-Delta behauptet. `verification.json`, beide Browserberichte und Export-Testlogs enthalten die tatsächlichen Resultate.

## Produktionsfreigabe

Sichere Entwicklungsänderungen und lokale Prüfungen sind autorisiert und erledigt. **Nur der Produktionsrelease muss mit den sechs geprüften Top-Angeboten und dem konkreten Owner-GO für Deployment/Händleraktivierung gekoppelt werden.** Die schriftliche Top-Erlaubnis vom 06.10.2026 bezieht die Bilder auf die DUFYND-/Top-Integration und den Kaufabschluss bei Top; sie verlangt keine Exklusivität des Duftprofils. Rabannes günstigere Perfumetrader-Option bleibt bestehen, das passende Top-Angebot kommt separat hinzu. Die öffentlichen neuen Bilder zeigen Top als konkrete Bildquelle.

Die visuelle Annahme aller sechs Bilder liegt bereits vor; keine weitere Fotoabnahme oder neue Händler-E-Mail ist erforderlich. Eine neue vollständige Prüfung der Programm-Nutzungsbedingungen wird nicht behauptet: `rights_checked_at` bleibt 28.09.2026, die konkrete schriftliche Top-Erlaubnis stammt vom 06.10.2026.

## Rücknahme und erneute Prüfung

Die 5+1-Patches beziehen sich auf PR #836, Basis-HEAD `5ffd422081bbec23d1892906f9f1186190e26de0`, mit dem dazugehörigen sechsfachen privaten Review- und Rendering-Delta. Nach weiteren Änderungen zunächst `git apply --reverse --check` verwenden. Kein erzwungener Kontext.

```bash
git apply --reverse --check release/dufynd-photo-wave-20261026/02-rabanne-original-after-matching-top-offer.patch
git apply --reverse release/dufynd-photo-wave-20261026/02-rabanne-original-after-matching-top-offer.patch
git apply --reverse --check release/dufynd-photo-wave-20261026/01-five-top-parfuemerie-originals.patch
git apply --reverse release/dufynd-photo-wave-20261026/01-five-top-parfuemerie-originals.patch
```

Nach Rücknahme den öffentlichen Export neu bauen. Angebots-Rollback und Deployment bleiben separate Schritte. Der Export-Negativtest ist aus einem fertig gebauten `storefront-web` aufrufbar; er stellt die lokale generierte Registry auch bei Fehlern bytegenau wieder her:

```bash
node ../../../release/dufynd-photo-wave-20261026/test-public-export-boundary.mjs
```
