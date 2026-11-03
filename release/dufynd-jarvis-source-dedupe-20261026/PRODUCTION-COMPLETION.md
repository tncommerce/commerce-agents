# Jarvis Source-Dedupe: Produktionsabschluss 26.10.2026

**Der begrenzte Datenbank-Fix ist produktiv angewendet und durch reguläre Cron-Läufe beobachtet.**
Projekt: `bqsdxaagklpkxioaqdqa`. Das konkrete Owner-GO vom 26.10.2026 deckte
den vorbereiteten Source-Dedupe-Fix ab. GitHub-Merge und Render-Deployment wurden
nicht ausgeführt. Es wurde kein Planner manuell gestartet und kein künstliches
Käufer-, Händler- oder Veröffentlichungsereignis erzeugt.

Sämtliche SQL-Inhalte einschließlich Apply-/Rollback-Dateien bleiben bytegleich.
Die Repository-Migration wurde nach Ausführung auf die tatsächliche Ledger-Version
umbenannt; ausführbare Pfadreferenzen, README und Manifest sind entsprechend
abgeglichen. Historische Angaben in den Proben beschreiben ihren damaligen
Vorbereitungsstand. Dieser Abschluss ist kein Auftrag zur erneuten Anwendung.

## Ausführung und exakte Zuordnung

- Freigegebener PR-HEAD: `7cc25aff0dd0152124b366e7624d7b6be00eab84`.
- Produktionsbranch unverändert: `7b793cf7ce1223967e66d768fcb7930ecdfc0e40`.
- Einmaliger Supabase-Aufruf: `apply_migration`, Name
  `jarvis_business_source_dedupe`, vollständige unveränderte `apply-body.sql`.
- Tatsächliche, vom Tool registrierte Migration: **`20261026122726`**.
  Die unveränderte Repository-Quelldatei heißt jetzt
  `supabase/migrations/20261026122726_jarvis_business_source_dedupe.sql`.
  Zum Apply-Zeitpunkt hieß sie `20261026083433_jarvis_business_source_dedupe.sql`.
  Die spätere reine Umbenennung verhindert einen erneuten versionsbasierten
  Apply unter der alten Dateiversion; sie verändert keine Datenbank-History.
- Apply-Antwort: `success=true`. Read-only Postflight:
  **26.10.2026, 12:27:42 UTC**.
- Planner-MD5: `8668638435b216b4c0dd9fa535448669`.
  Helper-MD5: `6b8852a51087ba57bf2222481e651bc7`.
  Beide Funktionen: Owner `postgres`, Security Invoker, EXECUTE ausschließlich
  für `postgres` und `service_role`.

| Unveränderte Datei | SHA-256 |
| --- | --- |
| Quellmigration | `65caae22624b26fd925d8e341a78696ed9e21e9b3ef45ced49d6335f15a04eb4` |
| `apply-body.sql` | `75b46ae9e5b9b2be16b0d10990b26666cabbd63e4ba0702168c47094152b8170` |
| `postflight.sql` | `10e1a137de3773100215252426a6630d87fb77e0bc88d4ac40d882af888c225b` |
| `rollback-body.sql` | `e6a371188f2872082e57f9b6102646ba85bc65f7f5394591f605cd77cd17be6b` |

[production-execution.json](production-execution.json) enthält die redigierte
Originalantwort, beide Postflight-Zeilen und ausschließlich den relevanten
History-Eintrag. Fremde Migrationshistorie und Transporthüllen sind nicht kopiert.

## Natürlich beobachteter Betrieb

Read-only Beobachtung um **12:30:16 UTC**:

| Regulärer Lauf | Beobachtung |
| --- | --- |
| Supervisor, 12:28 UTC | Erfolgreich; genau eine initiale `source-v1`-Baselineaufgabe angelegt, bereits `done`. |
| Supervisor, 12:30 UTC | Erfolgreich. |
| CEO-Growth-Loop, 12:30 UTC | Erfolgreich; Planner meldet `waiting_market_signal` / `wait_for_verified_merchant_clickout`. |

Nach diesen Läufen existierte weiterhin genau **eine** `source-v1`-Aufgabe.
Der Checkpoint blieb auf 12:28 UTC mit Source-Fingerprint
`f49f38130d6f8f5bd4783a6222f8420ba5920308b0fa0f3f53c5c838f0ee4011`.
Damit wurden im beobachteten Erst- und Folgezyklus keine zusätzlichen redundanten
Source-Audits erzeugt. Dies belegt den beobachteten Zeitraum, keine unbegrenzte
Zukunftsgarantie und keinen echten Affiliate-Clickout.

[production-natural-cron.json](production-natural-cron.json) enthält die genaue
SELECT-Abfrage und deren redigierte Originaldaten. Die Cron-Konfiguration wurde
nicht verändert. Vorhandene Schutzmechanismen blieben erhalten.

## PR-, Test- und Rollback-Status

[PR #839](https://github.com/tncommerce/commerce-agents/pull/839) war bei Ausführung
Ready for Review und unmerged. HEAD `7cc25aff…` war konfliktfrei mergebar, aber durch
das aktive Branch-Ruleset blockiert: sechs Required Checks, null Check-Runs und
null Statuskontexte auf diesem HEAD; kein Bypass. Die historische erfolgreiche
[CI #40303294857](https://github.com/tncommerce/commerce-agents/actions/runs/40303294857)
auf `3d272051c2ece547e3a5cff8f9b9bc76d61f8600` erfüllt diese HEAD-Bedingung nicht.

Bestehende Nachweise wurden wiederverwendet: 233 native PostgreSQL-Tests inklusive
31 Dedupe-Assertions sowie 28 isolierte Paket-/Rollback-Assertions. Kein neuer
CI- oder Regressionstestlauf für diesen reinen Nachweis-Commit. Lokal geprüft
wurden JSON-Lesbarkeit, die Zuordnung der Originalantworten, gültige Pfadreferenzen
und die unveränderten SQL-Checksummen. Manifest-Hashes der gezielt angepassten
Dokumentation und Pfadreferenzen wurden aktualisiert.

Das geprüfte Rollback-Paket bleibt unverändert und wurde nicht ausgeführt.
Bei einer später erforderlichen, separat freigegebenen Rücknahme wird genau
`rollback-body.sql` mit `apply_migration` und dem Namen
`jarvis_business_source_dedupe_rollback` verwendet. Es stellt ausschließlich den
gesicherten alten Planner wieder her; Helper, Checkpoint, Aufgaben und bisherige
History-Einträge bleiben erhalten. Kein allgemeines `db push`, kein History-Repair
und kein Replay alter Migrationen wurden durchgeführt. Die bereits zuvor
abweichenden älteren Repository-/Ledger-Versionen sind damit nicht behoben;
ein allgemeines `supabase db push` bleibt außerhalb dieses begrenzten Auftrags.

## Prüfsummen dieser Nachweise

| Datei | SHA-256 |
| --- | --- |
| `production-execution.json` | `b686857adaded42ae479318d94751fb1fd413fd7e5090e417cbd393ad1abe096` |
| `production-natural-cron.json` | `dd8d9f93e546433e0d0dd96eda6bf2ef116c29b38b412a68dddabf482e4f7a6c` |
