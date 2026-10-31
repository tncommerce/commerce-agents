# DUFYND · Produktions-Datenbank: Migrationshistorie gesperrt, 31.10.2026

**LIVE STATE GEWINNT · DELTA-ONLY · 0 € Zusatzkosten.** Nur technische
Nachvollziehbarkeit; keine Datenbankreparatur, kein Import, kein Angebot live.

## Das tatsächlich installierte private Angebotsschema

Die separate Owner-Freigabe umfasste **zwei Tabellen ohne Angebotsaktivierung**.
Die unveränderte, im Repo vorhandene Migration
`20261023221100_dufynd_runtime_offer_snapshots_v1.sql` wurde mit
SHA (Git-Blob) `e38419fe22e3624b43b367927531071cd09bf661`
angewandt. Supabase registrierte die ausgeführte Migration unter
**`20261031200428`** statt unter dem Repository-Dateinamen.
Die anschließend notwendige Rechtehärtung lief als Migration
**`20261031200548`** (`dufynd_runtime_offer_snapshot_acl_least_privilege`).

Live-Postflight: beide Tabellen **0 Zeilen**, RLS aktiv, keine Policies für
`anon`/`authenticated` und keinerlei SELECT-/INSERT-Rechte für diese Rollen.
Beide Trigger aktiv. `service_role` darf nur die vorgesehenen
SELECT-/INSERT-/UPDATE-Operationen an der Snapshot-Tabelle sowie
SELECT/INSERT am Audit ausführen, **kein DELETE oder TRUNCATE**. Beide
Triggerfunktionen sind SECURITY INVOKER, öffentlich nicht ausführbar.
Kein Angebot, Link, Bestand, Preis oder Laufzeitflag wurde aktiviert.
Static Website und API blieben unverändert live.

## Der wichtige globale Migrationsblocker

Read-only-Abgleich von `scentai-mvp` und Supabase Migration History:
**81** SQL-Dateien lokal; **166** Remote-Einträge. **77** lokale Namen
kommen remote semantisch vor, davon **74** unter einer anderen
Versionsnummer. **4** lokale Namen fehlen remote, **89** Remote-Namen
haben keine gleichlautende Datei. Im Remote-Verlauf kommt außerdem
`extend_dufynd_jarvis_learning_loop` mehrfach unter verschiedenen
Versionen vor.

Daraus folgt **NICHT**, dass alle Remote-Einträge fehlen oder noch ausgeführt
werden müssten. Insbesondere sind die beiden neuen Tabellen schon da.
`supabase migration list` vergleicht laut offizieller Dokumentation
**Versionsnummern, nicht SQL-Inhalte**. Ein naiver `supabase db push`
oder das blinde Verschieben/Umbenennen einzelner Dateien wäre hier nicht
freigegeben und könnte Duplikate verursachen.

## Prüfsperre ohne Datenbankzugriff

Nach sicherem, separat angefertigtem Export **nur der
Migrations-Metadaten** kann lokal geprüft werden:

```bash
python scripts/check_dufynd_migration_history.py \
  --local-dir supabase/migrations \
  --remote-json private-migration-list.json
```

`private-migration-list.json` muss die Form
`{"migrations":[{"version":"YYYYMMDDHHMMSS","name":"snake_case_name"}]}`
haben. Der Check blockiert bei fehlenden Remote-/lokalen Datensätzen,
doppelten Namen, abweichenden Versionen und unvollständigen Angaben.
Er enthält **keine Netzwerk- oder Datenbank-Aufrufe**, repariert nichts und
benötigt weder Zugangsschlüssel noch neue Dienste.

Für eine spätere wirkliche Reparatur: nur nach vollständigem Schema-/SQL-
Vergleich, dediziertem Rollback-/Backup-Nachweis und expliziter
DB-Migrationshistorienfreigabe. Sie muss die **gesamte** bereits
divergierende Historie behandeln und darf die installierten Tabellen nicht
neu erstellen. Supabase dokumentiert dafür das kontrollierte
`supabase migration repair --status applied|reverted`, nicht einen
pauschalen Neulauf.

Quelle: https://supabase.com/docs/reference/cli/supabase-migration-repair

## Commerce-Trennung

Die alten **14** Händlerbeobachtungen bleiben HOLD
(`merchant_purchase_control_not_confirmed`), ihre Quellzeiten und
SHA-256 bleiben original. Die drei späteren Kaufbedienungsbelege aus
31.10. (Rabanne Perfumetrader, Delina NOTINO, Bois Impérial Top) sind
**private Quellenkandidaten**, keine Import-/Veröffentlichungsfreigabe.
Für Delina ist die aktuelle CJ-Vertrags-/Trackinggeltung offen; bei Top
Parfümerie zeigt das private Partnerregister weiter
`tracking_ready=false`. Die drei Beobachtungen altern ab ihrer
ursprünglichen Versandauskunft und Produktseite und dürfen nicht
künstlich erneuert werden.

**Nächster sichere Arbeitsbereich:** aktuelle Netzwerkbelege und
angebotsspezifische Quellen validieren; die tatsächliche Angebotsimport-
und Aktivierungsentscheidung bleibt ausdrücklich separat.
