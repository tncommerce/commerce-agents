# Offene Originalbildquellen – 30.10.2026

Basis: `a3b35fd253831d5ea89590e7512d80445d132b94`, nach Integration von PR #859. Ausschließlich Quellenarbeit; keine neuen Originale freigegeben oder auf der Website veröffentlicht.

## Neu gewonnen

Für die 23 nach dem vorhandenen Top-Abgleich noch ungeklärten Quellen wurden gezielt andere bereits zugelassene Händler durchsucht. `source-candidates.json` enthält alle 23 Produkt-IDs mit Händlerseite, ausgewählter Variante, beobachtetem Medienlink und getrennten Restblockern:

- 17 konkrete Quellenkandidaten: 15 Notino, 2 Douglas.
- 16 mit passender Größe/Konzentration; bei Orientica Royal Blue/Royal Bleu ist zusätzlich der Namensabgleich offen.
- Absolu Aventus liegt als neuer Notino-Kandidat in EDP 100 ml vor. Der bisherige Top-Kandidat 75 ml bleibt ungeeignet und wird nicht ersetzt oder umgedeutet.
- Bei 6 Profilen fand die begrenzte Suche keinen qualifizierten Händler-Treffer. Dies ist keine globale Nichtexistenzaussage.

Öffentliche Händlerbilder sind dadurch nicht lizenziert. Für die 17 Kandidaten fehlen eine auf die Quelle anwendbare Bildnutzungsfreigabe, die Originaldatei-/Hashbindung und die vorgesehene visuelle Owner-Abnahme. Bei Tygar 125 ml wurde ein Douglas-Medienlink gefunden; der direkte Medienabruf scheiterte. Die öffentliche Recherche belegt keine aktuelle Preis-/Bestandsfrische. Es wurden keine Trackinglinks erzeugt.

## Vier bereits vorbereitete Originale

Die vorhandenen Händleroriginale für Aventus 100 ml, Explorer 100 ml, Prada L’Homme 100 ml und Naxos 100 ml wurden gemeinsam in einer privaten, fertig geprüften PDF-/HTML-Abnahmevorlage dargestellt. Die technische Rechte-/Hashprüfung vom 26.10. wurde übernommen und nicht erneut durchgeführt. Vierer-Zuordnung, sichtbare Originale und Abnahmestatus sind eindeutig. HTML-Anzeige bei 390/1440 px sowie beide PDF-Seiten wurden geprüft; keine externen Requests oder Anzeigenfehler. Alle vier persönlichen Bildabnahmen bleiben ausstehend. Historische generierte Cutouts sind keine Freigabe dieser Originale.

Bestehender technischer Nachweis: `artifacts/dufynd-wave2-discovery-20261026/four-photo-candidates.json`. Die private Vorlage ist kein Website-Release.

## Gezielter Perfumetrader-Inventarzugang

Der historische Providerbefund „Produktdaten = Nein“ wird nicht als aktueller Befund ausgegeben. Eine bekannte Perfumetrader-Feed-ID lag nicht vor; die Top-ID 91379 darf nicht für Advertiser 11672 verwendet werden.

Der neue `scripts/probe_dufynd_perfumetrader_feed_inventory.py` führt ausschließlich einen begrenzten GET der offiziellen Awin-Feedliste aus. Er verwendet den vorhandenen Reader mit Redirect-/Größenbegrenzung und gibt nur bereinigte Metadaten für Advertiser 11672 aus. Kein Produktfeeddownload, kein Bildimport, keine Änderung von Freigaben und keine Ausgabe von Schlüsseln oder Download-URLs. Fehler und fehlende Credentials werden geschlossen als Blocker dokumentiert; unbestätigte Antwortformate werden nicht als „kein Feed vorhanden“ gewertet.

Ein manueller Job im bestehenden Awin-Workflow ist ausschließlich auf `work/dufynd-image-sources-followup-20261030` begrenzt. Der bisherige Top-Job wird auf diesem Branch übersprungen; auf anderen Branches bleibt sein Ablauf unverändert. Standard-Ubuntu-Runner, fünf Minuten, `contents: read`, vorhandener Secretname, kein Installieren, Cache, Artefakt-Upload oder Scheduler. Die Repo-Sichtbarkeit ist public; Standardrunner sind dort kostenlos.

**Live-Inventarprüfung nicht ausgeführt.** Nach der separaten Render-Kostenprüfung brach die Browserverbindung ab. Die verbundene GitHub-App bietet in dieser Sitzung keinen Workflow-Dispatch. Es wurde kein alternativer automatischer Trigger eingerichtet und kein historischer Feedbefund als neue Beobachtung ausgegeben. Acht neue gezielte Offlinefälle für den Probe bestanden; frühere Suites wurden nicht wiederholt. Die abschließende Ausführung und ein aktueller Quellenzugangsnachweis bleiben offen.

## Abgrenzung

Keine Änderungen an öffentlichen Katalog-/Bildregistern, Angeboten, API, Scheduler, Broker, Supabase, Migrationen oder Produktionsflags. Kein Merge, Deployment, künstlicher Klick oder Kauf. Die neue Quellenmatrix ist von der bestehenden privaten 14er-Händlerübergabe getrennt. Der aktuelle Render-Kostennachweis liegt privat vor; Finanzdaten gehören nicht in diesen öffentlichen Branch.
