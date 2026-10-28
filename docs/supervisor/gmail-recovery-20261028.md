# Gmail recovery: one owner renewal, then a new complete observer run

## Lokaler Owner-Helfer: einmalige Gmail-Neuverknüpfung

Der vorhandene Broker benötigt zunächst einen privaten authentifizierten Start;
erst dessen Antwort enthält den kurz gültigen Google-Link. Dafür steht jetzt
`scripts/dufynd_gmail_owner_reauthorize.py` bereit. Der Helfer verwendet nur die
Python-Standardbibliothek und läuft auf dem **eigenen lokalen Desktop**. Er führt
keine Google-Freigabe aus und wartet auf keine Callback-Daten. Ein Broker-Deployment,
PR #802, neue Cloud-Ressourcen oder neue IAM-Rechte sind dafür nicht erforderlich.

### Vorbereitung im vorhandenen privaten Zugang

1. Den bereits bestehenden privaten Dienst im Projekt
   `dufynd-private-broker-01`, Region `europe-west3`, Service
   `dufynd-private-observer` ansehen. Aus seiner vorhandenen Konfiguration nur
   **`BROKER_ORIGIN`** und **`GOOGLE_CLIENT_ID`** ablesen. Diese beiden Werte sind
   keine geheimen Schlüssel. Keine neue URL ableiten und keinen Dienst anlegen.
   Der Helfer akzeptiert ausschließlich den vorhandenen HTTPS-Cloud-Run-Origin
   dieser Service-Namensfamilie, ohne Pfad, Port, Query oder Fragment.
2. Den bestehenden Owner-Key im eigenen privaten Passwortmanager bereithalten.
   Er gehört **nicht** in einen Befehl, eine Umgebungsvariable, eine Datei, einen
   Screenshot oder den Chat. Der Helfer liest ihn ausschließlich verdeckt im
   lokalen Terminal. Er liest selbst keine Secret-Manager-Werte.
3. Die geprüfte Skriptversion auf dem eigenen Rechner verwenden. Python 3.11 oder
   neuer und ein lokaler grafischer Browser reichen aus; kein `pip install` nötig.
   Nicht in GitHub Actions, einer aufgezeichneten Remote-Sitzung oder einer
   browserlosen Cloud Shell ausführen. Der Deployment-Helfer
   `deploy_dufynd_private_broker.sh` ist hierfür **nicht** erforderlich.

### Windows / PowerShell

Im Repository-Verzeichnis ausführen; die beiden Platzhalter vorher ausschließlich
durch die eben abgelesenen **nicht geheimen** Werte ersetzen:

```powershell
py -3 scripts\dufynd_gmail_owner_reauthorize.py --broker-origin "VORHANDENER_BROKER_ORIGIN" --client-id "OEFFENTLICHE_GOOGLE_CLIENT_ID"
```

Mit macOS oder einem Linux-Desktop lautet derselbe Aufruf `python3
scripts/dufynd_gmail_owner_reauthorize.py` mit denselben zwei Optionen. Unter Linux
wird ein grafischer Desktop mit `xdg-open` benötigt. Eine gesetzte
`BROWSER`-Überschreibung wird aus Sicherheitsgründen nicht ausgeführt. Bei
gesetztem **`SSLKEYLOGFILE`** bricht der Helfer bereits vor der Schlüsseleingabe
ab; diese lokale TLS-Diagnosekonfiguration muss vor dem Start entfernt sein.

1. Den angezeigten Broker-Origin mit dem vorhandenen privaten Dienst vergleichen.
   Nur dann den einmaligen Start mit **`ja`** bestätigen.
2. Den Owner-Key in die **unsichtbare lokale Eingabe** einfügen. Der Helfer sendet
   genau einen HTTPS-POST an `/owner/oauth/gmail/start`. TLS-Prüfung bleibt aktiv;
   Weiterleitungen, Proxy-Übernahme aus der Umgebung und automatische Wiederholungen
   sind gesperrt. Der TLS-Kontext übernimmt keine Keylog-Datei aus der Umgebung.
   Falls verdeckte Eingabe nicht möglich ist, bricht er ab.
3. Der Helfer prüft die Antwort: ausschließlich Googles fester OAuth-Endpunkt,
   die zuvor angegebene Client-ID, der eigene exakte Callback, nur `gmail.metadata`,
   offline-Zugriff, PKCE S256, einmaliger Zustand und keine zusätzlichen Parameter.
   Erst nach einem zweiten lokalen **`ja`** öffnet er diesen Link im Browser.
   Link, Zustand und Schlüssel werden nicht auf stdout/stderr ausgegeben oder in
   eine Datei des Helfers geschrieben. Unter Linux/macOS startet der Helfer den
   festen Betriebssystem-Launcher ohne Shell und mit stdin/stdout/stderr auf
   `DEVNULL`; auch dessen Fehlerausgaben können den Link nicht im Terminal
   ausgeben. Windows verwendet die native URL-Zuordnung. Die Sitzung gilt
   insgesamt zehn Minuten ab Start.
4. Im Browser das bereits konfigurierte Postfach wählen und die bestehende
   Metadaten-Berechtigung einmal bestätigen. Erfolg ist die Callback-Antwort
   **`{"status":"authorized"}`**. Die vorherige Meldung „Google-Öffnung angefordert“
   allein bestätigt noch keine erfolgreiche Freigabe.
5. Danach genügt die Rückmeldung **„Gmail autorisiert“**. Keine Adresszeile,
   Callback-URL, Codes, Schlüssel oder Token teilen. Die nachfolgende echte
   Read-/Ingest-/ACK-/Finalize-Prüfung übernimmt wieder der technische Ablauf.

Bei einem Fehler zeigt der Helfer nur einen festen redigierten Grund. Er öffnet
keine unvalidierte URL und wiederholt den privaten Start nicht. Ein abgebrochener
oder abgelaufener Start ist kein Grund für Login-Schleifen: zuerst den angezeigten
Grund im privaten Zugang klären. Der Helfer speichert nichts dauerhaft; er kann
allerdings keine sichere Löschung aus dem Python-Prozessspeicher garantieren.

### Prüfung des Helfers

**Aktueller, im Root-Review geprüfter Nachweis vom 28.10.2026:**
**90/90 gezielte Helper-Tests bestanden** unter den bestehenden
Repository-Abhängigkeiten; Ruff und `git diff --check` ebenfalls erfolgreich.
Die beiden Review-Funde zu TLS-Keylogging und Launcher-Fehlerausgaben sind dabei
behoben und mit eigenen Regressionen abgedeckt. Das ist ein lokaler
Sicherheitsnachweis des Helfers, kein Nachweis einer ausgeführten Gmail-Freigabe.

Die gezielten Tests verwenden den echten `urllib`-Opener einschließlich
HTTP-Fehler-/Redirect-Verarbeitung mit einer kontrollierten HTTPS-Grenze. Sie
decken Weiterleitungen ohne Weitergabe des Owner-Headers, Antwortgrößen, falsche
OAuth-Ziele/Client-IDs/Scopes/Callbacks, doppelte Parameter, Terminal-/Browser-
Grenzen und die Redigierung von Fehlern ab. Weitere Regressionen verhindern
TLS-Keylog-Dateien und führen einen echten lokalen Test-Kindprozess aus, der
seine ausschließlich fingierte OAuth-URL absichtlich nach stdout und stderr
schreibt: keine dieser Ausgaben erscheint im Terminal. Ein zusätzlicher positiver Test
verwendet den wirklichen `OAuth.start()`-Vertrag des bestehenden Brokers.
Kein Test führt einen echten Consent-Start oder einen Google-Aufruf aus.

## Historische Entwicklungsnachweise vor dem produktiven Release #843

Alle nachfolgenden Unterabschnitte dokumentieren die frühere Vorbereitung von
**#843**, einschließlich damaliger Aussagen zu noch fehlender CI, PR-Publikation,
Merge und Deployment. Sie beschreiben weder den heutigen Release-Status noch
eine neue Freigabeschranke für den lokalen Owner-Helfer. Der dort beschriebene
Run-/Attempt-Schutz ist inzwischen über
#843 auf `7f63836c1e1f837e1dc72e3ab0e12090a97d8112` produktiv; das ersetzt keinen
echten Nachweis einer erneuerten Gmail-Freigabe.

Historical evidence date: 28 October 2026, before release #843. That patch was
prepared locally against production commit
`89aae8925e606caa33f8f7dafa3edbeafab32c3c`. That preparation did not perform OAuth,
read a credential, modify activation, deploy a broker or create a scheduler.

### Historical live delta during #843 preparation and the scope of PR #802

- [PR #802](https://github.com/tncommerce/commerce-agents/pull/802) is still draft
  at `39978a57820e7dbd68d22b803c748fe46a556554`, with five changed files. Its
  existing [CI 39070073648](https://github.com/tncommerce/commerce-agents/actions/runs/39070073648)
  succeeded. Those results were reused, not rerun.
- A local merge calculation against exact production `89aae892…` is conflict-free:
  combined tree `36d5f2a45eee75dc8cbfcaff76582ef21faafebc`. This is mechanical
  compatibility evidence, not a new runtime or deployment acceptance.
- #802 adds an independent, disabled-by-default Google OIDC refresh trigger.
  It does not repair a revoked grant, perform ingestion, ACK a Gmail cursor, or
  finalize an acceptance session. It is not a prerequisite for the immediate
  credential recovery. Its separate Cloud Scheduler/IAM/cost gates remain intact.
- The latest production observer run returned by the GitHub API during this
  review was [40662804800](https://github.com/tncommerce/commerce-agents/actions/runs/40662804800),
  attempt 1, created at 09:15:18 UTC on `89aae892…`.
  [Read job 122729756385](https://github.com/tncommerce/commerce-agents/actions/runs/40662804800/job/122729756385)
  reported `gmail_1:revoked` at 09:15:43 UTC. The failure-receipt job succeeded;
  ingest, ACK, and finalize were skipped. No Gmail recovery is established.
- A configured five-minute dispatcher interval does not prove five-minute
  executions. Recovery must cite a new actual workflow run, not infer one from
  cron configuration or reuse the old failed run's receipt.

### Historical handoff defect and bounded fix released in #843

The failure path already checked `run_attempt`. The successful path checked only
`run_id` and SHA, while its filtered-read, ACK-plan and ACK-receipt artifact names
also omitted the attempt. A later attempt could select earlier-attempt evidence.
Re-uploading the same name is also incompatible with immutable Actions artifacts;
see the official [artifact migration guidance](https://github.com/actions/upload-artifact/blob/main/docs/MIGRATION.md).

An offline reproduction against unchanged `89aae892…` set the running attempt to
2 while supplying source-attempt-1 evidence. The fake control plane accepted one
health projection, four captures, six ACK requests and one finalize call. These
were local fakes with zero network requests, not production writes.

The patch now:

1. Binds every successful handoff to the expected `run_id`, SHA **and attempt**,
   before health projection, capture, OIDC retrieval, ACK or finalization.
2. Includes `github.run_attempt` in all three success-artifact names and their
   exact downloads, matching the already protected failure-artifact path.
3. Requires `GITHUB_RUN_ATTEMPT` or the corresponding explicit CLI argument at
   operational entry points. Missing provenance fails before bridge creation or
   network access.

No credential, OAuth scope, broker endpoint, provider identity, activation gate,
database function or scheduled job changes. ACK remains contingent on all four
durable captures; three idempotent ACK rechecks remain required before finalize.

### Existing owner protocol documented during #843 preparation

The private broker reports a terminal revoked state. Its refresh implementation
intentionally refuses that state; repeating refresh jobs cannot restore it.

The required intervention is **one fresh authorization of the existing private
broker using the mailbox already configured for it**:

1. The owner or existing authorized private-project operator uses the existing
   owner-only `POST /owner/oauth/gmail/start` from their secure local client. The
   owner key stays in that private environment. It is not copied into ChatGPT,
   GitHub Actions, Supabase, this repository or a task packet.
2. The owner opens the newly returned Google authorization URL, selects the
   configured mailbox and consents once to the existing exact
   `https://www.googleapis.com/auth/gmail.metadata` scope. No broader mail scope,
   new client or new service account is needed for this recovery.
3. The existing callback consumes the short-lived PKCE/state session once,
   verifies the mailbox and scope, and stores the new credential atomically in
   the private encrypted vault. Codes, callback queries, tokens and private keys
   must not be pasted into a handoff. Existing callback-log protections remain
   mandatory. Use a fresh authorization URL if that single session has expired;
   do not replay a callback or start recurring login attempts.

The observed reason does not establish why Google invalidated the grant.
Google documents revocation, Gmail-scope password changes and other causes.
For an external OAuth app still in **Testing**, non-basic scopes can result in
a seven-day refresh-token lifetime. The private-project operator should check
that existing app's publishing/policy metadata once before treating consent as
a durable repair. The app's actual status was not read in this review; no
publishing or policy setting was changed. See [Google's refresh-token guidance](https://developers.google.com/identity/protocols/oauth2#expiration).

### Full-chain acceptance contract, unchanged since #843 preparation

Use a **new workflow run ID** from the existing trusted production observer
workflow. The existing dispatcher may supply it; if delayed, the existing
owner-authorized manual workflow is the bounded fallback. No new automation or
credential-sharing capability is required.

- Read: current production SHA; fixed Render service plus all three allowlisted
  Gmail threads; healthy/expiring metadata captured after those reads.
- Ingest: the current run/attempt artifact only; fresh bounded health projection;
  an acceptance session in `recurring_read` mode when both existing activations
  remain enabled; four accepted durable captures.
- ACK: the three exact accepted digests; first-pass acknowledged plus duplicate
  counts total three; all three second-pass replies are duplicate.
- Finalize: the same run/SHA/attempt; matching ACK receipt; session reaches
  `activated` with a real `finalized_at`, all expected captured observers and
  `activation_changed:false` for recurring recovery.
- Observation: all three Gmail `last_success_at` timestamps actually advance.
  Only then report the full observer chain recovered. This still does not prove
  a new merchant reply, a task completion, a clickout, a sale or a commission.

The database keeps one acceptance identity per `run_id` and rejects a different
attempt after a session has begun. This guard is deliberately unchanged. After
partial ingestion/ACK, use a new complete run ID; do not reuse an old acceptance
or re-run only later jobs with prior-attempt artifacts. A second attempt before
any acceptance began can use its own newly produced evidence. Neither case
requires repeated owner consent once the credential is healthy.

### Historical verification and pre-release gate for #843 — superseded

The normal integration gate described below was subsequently completed by
[#843](https://github.com/tncommerce/commerce-agents/pull/843):
[CI 40669372863](https://github.com/tncommerce/commerce-agents/actions/runs/40669372863)
passed all six required checks before the protected merge and production rollout.
The bullets below preserve the earlier preparation record; they are not current
claims that #843 remains unpublished, untested or undeployed.

- 72 focused Python cases passed, including 13 new attempt-boundary cases:
  old/future attempt rejection before side effects, successful current-attempt
  complete handoff with fake OIDC/ACK/control plane, missing-attempt rejection,
  and matching unique producer/consumer artifact names across attempts.
- Existing affected read, independent Render recovery, ingest, ACK, finalize
  and workflow tests were included. Ruff, formatting and `git diff --check` passed.
- The unchanged database acceptance contract already passed in production
  release CI [40661816326](https://github.com/tncommerce/commerce-agents/actions/runs/40661816326)
  (262 PostgreSQL tests). No database migration is included in this patch.
- During that earlier preparation review, no remote CI, PR publication, merge,
  workflow dispatch, credential read, consent, activation or deployment was performed.
- The then-pending gate required normal CI on the final integrated head and
  coordination with the active release; #843 subsequently satisfied that gate.
  Local fake success still does not constitute an actual Gmail recovery receipt.

Focused local command (existing isolated Python environment; no package install):

```sh
PYTHONPATH=commerce-common:merchant-agent/core:shopping-agent/core \
  /tmp/dufynd-venv/bin/pytest -q \
  tests/test_dufynd_private_observer_attempt_boundary.py \
  tests/test_dufynd_private_observer_ingest.py \
  tests/test_private_broker_observer_ack.py \
  tests/test_dufynd_private_observer_finalize.py \
  tests/test_dufynd_private_observer_workflow.py \
  tests/test_dufynd_render_observer_recovery.py \
  tests/test_private_broker_observer_read.py
```
