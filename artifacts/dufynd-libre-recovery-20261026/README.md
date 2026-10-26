# Libre 90 ml: freigegebene Angebotsidentität, frischer Datenkandidat

**Vorbereitet, nicht angewendet.** Die öffentliche DUFYND-API lieferte am
26.10.2026 um 11:39:34 Uhr Berlin kein kaufbares Libre-Angebot. Der kanonische
Notino-Beleg vom 20.10. war abgelaufen. Dies ist kein Nachweis eines Codefehlers.

Ein frischer normaler Browseraufruf der bereits freigegebenen exakten
[Notino-Produktseite](https://www.notino.de/yves-saint-laurent/yves-saint-laurent-libre-eau-de-parfum-fuer-damen/p-15968532/)
bestätigte am **26.10.2026 um 11:42:37.210 Uhr Berlin**:

- Yves Saint Laurent Libre, Eau de Parfum, **90 ml**, nachfüllbarer Flakon;
- sichtbarer Händlercode `VZR11010`, ausgewählte JSON-LD-SKU `YSLLBRW_AEDP10`,
  GTIN `3614272648425`;
- **130,00 EUR**, verfügbar, DHL nach Deutschland gratis, Gesamtpreis 130,00 EUR;
- der günstigere 100-ml-Eintrag für 128 EUR gehört zu einer anderen Variante.

Die unveränderte vorhandene CJ-Route und Produktfreigabe werden vom bestehenden
Importer geprüft. Keine neue Affiliate- oder Bildfreigabe wird abgeleitet.
Ein tatsächlicher Affiliate-Clickout, Warenkorb oder künstliches Analytics-Ereignis
wurde nicht ausgelöst. Der frühere HTTP-403 und die Suchcache-Antwort waren **keine**
Quelle für den neuen Zeitstempel; maßgeblich ist der anschließend gelungene
direkte Browseraufruf mit DOM und JSON-LD.

## Dateien und Nachweis

- `source-observation.json`: ausgewählte Originalquellen-Fakten und SHA256 der
  vollständigen Browserbeobachtung im zugehörigen Review-Bundle;
- `batch-input.json`: eine Zeile für den bestehenden Dry-run-Importer aus PR #837;
- `canonical-before.json`: unveränderte kanonische Zeile und ausdrücklich
  unbekannter bisheriger Runtime-Zustand;
- `dry-run.json`: tatsächliche erfolgreiche Importvorbereitung, keine Anwendung;
- `validation.json`: zwölf bestandene Prüfungen dieses konkreten Kandidaten;
- `verify-candidate.py`: reproduzierbare Offline-Prüfung mit der bestehenden
  Release-, Runtime- und Kundendarstellungslogik.

Getestete Basis: `a4f79726bc55fa579909e2f4b7955b361e474814`.
Nur dieser neue Kandidat wurde geprüft; die bereits bestandene vollständige CI
wurde nicht erneut gestartet. Die Validierung prüft die historische Beobachtung
zum Erfassungszeitpunkt. Der normale Dry-run verwendet dagegen die tatsächliche
aktuelle Uhrzeit und weist den Kandidaten nach Ablauf zurück.

```bash
python -m scripts.prepare_dufynd_runtime_offer_batch \
  --evidence artifacts/dufynd-libre-recovery-20261026/batch-input.json
PYTHONPATH=. python artifacts/dufynd-libre-recovery-20261026/verify-candidate.py
```

Batch-ID: `notino-libre-20261026T104237Z`.

Batch-SHA256:
`6820e001e75663dcf689810748588784b6538ef6997e0b3ade00e95ea4637996`.

**Gültigkeitsende: 29.10.2026, 11:42:37.210 Uhr Berlin / 10:42:37.210 UTC.**
Die vorhandene Grenze ist bis zu diesem Zeitpunkt inklusive gültig, danach
abgelaufen. Eine Freigabe nach Ablauf benötigt eine neue echte Händlerbeobachtung;
dieses Paket darf nicht durch Änderung nur des Zeitstempels verlängert werden.

## Anwendung erst nach konkretem Owner-GO

Dieser Commit verändert keine kanonischen Angebotsdaten, produktiven Tabellen,
Routing-Flags, Migrationen oder Umgebungsvariablen. `decision: verified` bestätigt
die vorbereitete Quellenbeobachtung, keine Produktivaktivierung.

Vor einem gesondert genehmigten Import muss die ausführende Stelle:

1. Die aktuelle Basis und den Rollout von PR #837 samt notwendiger Migration und
   Runtime-Konfiguration prüfen. Ein vorbereiteter Datensatz aktiviert diese
   Infrastruktur nicht.
2. Unmittelbar vor dem Schreiben die vorhandene Runtime-Zeile für genau
   `notino-ysl-libre-edp-90` oder ihre belegte Abwesenheit sichern. Die leere
   öffentliche API ist **kein** Nachweis einer fehlenden Tabellenzeile.
3. Den normalen Dry-run erneut mit aktueller Uhrzeit ausführen und ein konkretes
   GO für exakt Batch-ID und Batch-SHA256 verwenden. Der vorhandene Importer
   verlangt denselben vollständigen Wert als Argument und in seiner
   `DUFYND_OFFER_BATCH_OWNER_GO`-Freigabevariable. Hier wurde kein GO gesetzt.
4. Nach genehmigter Anwendung den eingebauten ungekachten Datenbank-Readback
   bestätigen und anschließend die normale öffentliche Angebots-API prüfen;
   kein Affiliate-Clickout ist dafür erforderlich. Bei unbestätigtem Schreibstatus
   zuerst den Zustand lesen, niemals blind erneut importieren.

## Rücknahme vorbereiten

Dieses Paket hat nichts zu löschen oder zurückzusetzen. Für einen späteren
genehmigten Import gilt: Vorherzustand sichern, Rücknahme auf **diese eine Zeile**
begrenzen und nur ausführen, wenn die aktuelle Zeile noch exakt dem importierten
Beleg entspricht. Bei zwischenzeitlich neuerem Händlerbeleg anhalten, ihn nicht
überschreiben. Existierte zuvor eine Zeile, ihren tatsächlich gesicherten Inhalt
wiederherstellen; andernfalls nur diese neu eingefügte Zeile entfernen. Das
auditierte Original nicht löschen. Kein globales Deaktivieren des Runtime-Kanals
und keine Rücknahme anderer Händlerangebote. Auch dieser Produktivschritt benötigt
konkretes GO.
