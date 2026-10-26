# Jarvis: Merge-, Migrations- und Rollback-Paket

**Datenbank-Fix am 26.10.2026 produktiv angewendet; kein Merge oder Deployment.**
Projekt `bqsdxaagklpkxioaqdqa`. Aktueller Status und redigierte Originalnachweise:
[PRODUCTION-COMPLETION.md](PRODUCTION-COMPLETION.md). Die nachfolgende Anleitung
dokumentiert die Vorbereitung des bereits ausgeführten Pfads; nicht erneut anwenden.
Merge-/Deployment-GO und SQL-GO sind getrennt. Pushes auf `scentai-mvp` lösen
bestehende Workflows aus; angebundenes Render-Autodeployment kann zusätzlich
deployen. Deshalb ist bereits der produktive Merge eine Freigabegrenze.

## Basis und wiederverwendete Nachweise

- Produktion: `7b793cf7ce1223967e66d768fcb7930ecdfc0e40`.
- Ursprünglich geprüfter Scheduler-HEAD von PR #839:
  `e571331222c7649a49c2758de432d6f21d6b9825`. Bei Ausführung enthielt der
  freigegebene HEAD `7cc25aff0dd0152124b366e7624d7b6be00eab84` zusätzlich dieses
  Releasepaket; der PR war Ready for Review und blieb unmerged.
- [Native CI 40303294857](https://github.com/tncommerce/commerce-agents/actions/runs/40303294857),
  Integrationscommit `3d272051c2ece547e3a5cff8f9b9bc76d61f8600`: 233 native
  PostgreSQL-Tests bestanden, einschließlich der vorhandenen 31 Dedupe-Assertions.
  Diese Nachweise wurden wiederverwendet; kein neuer CI-Lauf.
- Unveränderte Quelldatei:
  `supabase/migrations/20261026122726_jarvis_business_source_dedupe.sql`, SHA-256
  `65caae22624b26fd925d8e341a78696ed9e21e9b3ef45ced49d6335f15a04eb4`.
  Nach Ausführung wurde ausschließlich die Dateiversion von `20261026083433` auf
  die tatsächliche Ledger-Version `20261026122726` umbenannt. Der Inhalt blieb
  bytegleich; eine spätere versionsbasierte Migration soll sie nicht erneut spielen.
- Read-only Sicherung **26.10.2026, 11:37:35 Berlin**: PostgreSQL 17.6;
  `production-baseline.json` enthält die vollständige Planner-Funktion, Owner
  `postgres`, INVOKER, `search_path=public`, ACL nur `postgres`/`service_role`.
  Planner-MD5 `229acd42dc117f9419a750aa3b52f67c`.
- Read-only Abgleich **11:38:28 Berlin**: neuer Helper fehlt, Dedupe-Checkpoint
  hat null Zeilen, History-Version `20261026083433` fehlt. Kein Planner aufgerufen.

## Konkreter Freigabe- und Ausführungspfad

1. Unmittelbar vor einem freigegebenen Merge PR-HEAD und Produktions-SHA erneut
   abgleichen. Gegen die oben genannte Basis plus ausschließlich diesem Release-
   Paket ist kein Konflikt bekannt. Fremde Änderungen separat prüfen; nie erzwingen.
   Den gewünschten Merge einschließlich möglicher Deployment-Folgen ausdrücklich
   freigeben lassen. Ein Entwicklungs-GO ist dafür nicht ausreichend.
2. Vor dem separaten SQL-GO das aktuelle Projekt, `list_migrations` und die exakte
   Altdefinition/ACL read-only erneut abgleichen. Der Guard prüft sie nochmals
   atomar innerhalb der freigegebenen Änderung. Bei Drift nicht überschreiben.
3. Nach konkretem SQL-GO **genau einen** Aufruf über die vorhandene Supabase-
   Verbindung vorbereiten; die aktuelle Tool-Signatur wurde read-only überprüft:

   ```text
   apply_migration(
     project_id = "bqsdxaagklpkxioaqdqa",
     name = "jarvis_business_source_dedupe",
     query = vollständiger unveränderter Inhalt von apply-body.sql
   )
   ```

   `apply-body.sql` ist eine einzelne atomare PostgreSQL-Anweisung. Sie setzt
   `lock_timeout=2s`/`statement_timeout=30s`, übernimmt denselben Advisory-Lock
   wie der Planner und prüft Definitionen, Owner, ACLs und Abhängigkeiten.
   Der eingeschlossene Scheduler-Code entspricht bytegleich der geprüften
   Quelldatei. Preflight, DDL und Postflight scheitern oder gelingen gemeinsam.
   Kein Task, Checkpoint, Cron, Händlerstatus oder Veröffentlichungsbeweis wird
   durch dieses Installationspaket geschrieben.
   `lock_timeout` begrenzt nachfolgende Lock-Wartezeiten. Das innerhalb der
   laufenden DO-Anweisung gesetzte `statement_timeout` belegt **keine garantierte
   30-Sekunden-Gesamtlaufzeit** dieser Anweisung; Transport-/Session-Timeouts des
   produktiven Endpunkts wurden nicht ausgeführt oder getestet.
4. Erfolg nicht allein aus der Tool-Antwort ableiten: `postflight.sql` read-only
   ausführen und mit `list_migrations` den **tatsächlich vom Tool erzeugten**
   History-Eintrag sichern. Erwartet: Planner-MD5
   `8668638435b216b4c0dd9fa535448669`, Helper-MD5
   `6b8852a51087ba57bf2222481e651bc7`, weiterhin private EXECUTE-ACLs.
   Projekt, reale History-Version, Payload-SHA und unveränderten Source-SHA im
   Freigabeprotokoll miteinander verknüpfen. Nicht behaupten, das Tool müsse die
   Repository-Dateiversion `20261026083433` übernehmen.
5. Den nächsten ohnehin stattfindenden Supervisor-Durchlauf beobachten. Keine
   künstlichen Planner-, Buyer- oder Publication-Aufrufe. Ein erstes begrenztes
   Baseline-Audit ist vorgesehen; unveränderte Originaldaten dürfen danach keine
   weiteren `source-v1`-Audits erzeugen.

## Bereits bestehende Migrationshistory-Abweichung

`production-migration-history.json` enthält 147 live gelesene Version-/Namenspaare;
der letzte Eintrag ist `20261021130229`. Mehrere alte Dateiversionen unterscheiden
sich schon heute vom Repository, etwa Analytics-Retention: live `20261015185527`,
Repo `20261015180054`. Deshalb ist ein allgemeines `supabase db push` aus dem
Repository **kein freigegebener oder funktionsfähiger Release-Pfad für dieses Paket**.

Der begrenzte `apply_migration`-Aufruf wendet ausschließlich diese konkrete
Payload an und registriert sie selbst. Kein `migration repair`, kein `--include-all`,
kein Replay alter Migrationen, kein DB-Reset, keine erfundenen History-Dateien und
keine manuellen Änderungen der History-Tabelle. Die Zuordnung der tatsächlich
erzeugten neuen Version wird anschließend explizit dokumentiert. Eine spätere
allgemeine Bereinigung der historischen Repository-/DB-Zuordnung ist ein eigener
Auftrag; sie ist keine Voraussetzung für diesen einzelnen versionierten Tool-Aufruf.

## Rollback nach separatem GO

Nur die exakt gesicherte Planner-Funktion wird wiederhergestellt. Helper,
Checkpoint und bestehende Aufgaben bleiben erhalten. Der alte stündliche Planner
ist danach wieder aktiv; das ist die bewusste Rücknahme der Korrektur.

```text
apply_migration(
  project_id = "bqsdxaagklpkxioaqdqa",
  name = "jarvis_business_source_dedupe_rollback",
  query = vollständiger unveränderter Inhalt von rollback-body.sql
)
```

Auch der Rollback ist eine atomare Anweisung mit exakten Vor-/Nachbedingungen und
erhält einen neuen echten History-Eintrag. Erwarteter Planner-MD5 danach:
`229acd42dc117f9419a750aa3b52f67c`. Die ursprüngliche History bleibt bestehen;
keine Aufgaben löschen oder zurücksetzen. Vor einer späteren Reaktivierung
die neue Freigabe und Live-Basis prüfen; der erhaltene Checkpoint wird weiterverwendet.

`apply.sql`/`rollback.sql` sind die vollständigen Transaktionsfassungen für die
isolierte Probe. Sie werden **nicht zusätzlich produktiv ausgeführt**. Die
gewählte produktive Schnittstelle ist ausschließlich `apply_migration` mit den
atomaren Body-Dateien und konkretem Owner-GO.

## Neue Prüfungen

`release-rehearsal.json`: **20 neue PostgreSQL-WASM-Assertions**, insbesondere
Apply → Rollback → Reapply, exakte Definition/ACL/Owner-Wiederherstellung,
bytegleiche Business-Daten, Ablehnung abweichender Rollen/ACLs/Helper und fehlender
Abhängigkeiten sowie atomare Rücknahme bei absichtlich fehlschlagendem Postflight.
Die bereits bestandene native CI und die 31 Dedupe-Assertions wurden nicht wiederholt.
Separate Prüfung der atomaren Tool-Payloads: `migration-body-rehearsal.json`.

Grenze der vorbereitenden Proben: Offline PostgreSQL-WASM, kein nativer
Parallelverbindungstest. Der später tatsächlich ausgeführte Supabase-Transport
ist im Produktionsabschluss belegt. Checksummen stehen in `manifest.json`.
Die [offizielle MCP-Dokumentation](https://supabase.com/docs/guides/ai-tools/mcp)
beschreibt die verwendeten Apply-/List-Werkzeuge; die aktuelle Tool-Signatur und
die offizielle API-Implementierung wurden für diesen Ausführungspfad gelesen.
