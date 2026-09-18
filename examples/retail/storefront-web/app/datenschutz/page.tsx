// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

import LegalFooter from "@/components/LegalFooter";
import { legal, legalLocation } from "@/lib/legal";

export const metadata = {
  title: "Datenschutz",
  description: "Datenschutzhinweise für die Nutzung von SCENTAI.",
  alternates: {
    canonical: "/datenschutz",
  },
  robots: {
    index: false,
    follow: true,
  },
};

export default function DatenschutzPage() {
  return (
    <main className="min-h-screen bg-(--ground) px-4 py-10 text-(--ink) sm:px-6">
      <div className="mx-auto max-w-3xl">
        <article className="rounded-2xl border border-(--line) bg-(--card) p-6 shadow-(--shadow-sm) sm:p-8">
          <a href="/" className="text-[13px] font-semibold text-(--accent-ink) hover:underline">
            ← Zurück zu SCENTAI
          </a>

          <h1 className="mt-5 text-3xl font-semibold tracking-[-0.03em]">Datenschutzerklärung</h1>
          <p className="mt-2 text-[13px] text-(--ink-soft)">Stand: September 2026</p>

          <div className="mt-6 space-y-7 text-[15px] leading-7 text-(--ink-2)">
            <section>
              <h2 className="font-semibold text-(--ink)">1. Verantwortlicher</h2>
              <p className="mt-1">
                {legal.businessName}
                <br />
                Inhaber: {legal.ownerName || "—"}
                <br />
                {legal.street || "—"}
                <br />
                {legalLocation || "—"}
                <br />
                Deutschland
                <br />
                E-Mail:{" "}
                {legal.email ? (
                  <a className="text-(--accent-ink) hover:underline" href={`mailto:${legal.email}`}>
                    {legal.email}
                  </a>
                ) : (
                  "—"
                )}
              </p>
            </section>

            <section>
              <h2 className="font-semibold text-(--ink)">2. Hosting und Bereitstellung der Website</h2>
              <p className="mt-1">
                SCENTAI wird über Render bereitgestellt. Beim Aufruf der Website können technisch
                notwendige Verbindungsdaten verarbeitet werden, insbesondere IP-Adresse, Zeitpunkt
                des Zugriffs, angeforderte Ressource und technische Angaben zum verwendeten Browser
                oder Endgerät. Diese Verarbeitung dient der sicheren und zuverlässigen Bereitstellung
                des Dienstes.
              </p>
              <p className="mt-2">
                Anbieter: Render Services, Inc. Weitere Informationen findest du in der{" "}
                <a
                  href="https://render.com/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-(--accent-ink) hover:underline"
                >
                  Datenschutzerklärung von Render
                </a>
                .
              </p>
            </section>

            <section>
              <h2 className="font-semibold text-(--ink)">3. Nutzung der SCENTAI-Beratung</h2>
              <p className="mt-1">
                Wenn du die Duftberatung verwendest, werden deine Eingaben sowie der für die laufende
                Unterhaltung erforderliche Gesprächskontext verarbeitet, damit SCENTAI deine Anfrage
                beantworten und passende Produkte darstellen kann. Bitte übermittle in der Beratung
                keine sensiblen oder für die Duftempfehlung nicht erforderlichen personenbezogenen Daten.
              </p>
              <p className="mt-2">
                Für die Generierung der Antworten nutzt SCENTAI die Anthropic API. Dabei werden die für
                die Bearbeitung erforderlichen Inhalte an Anthropic übermittelt. Anthropic gibt für die
                kommerzielle API standardmäßig an, Ein- und Ausgaben innerhalb von 30 Tagen zu löschen,
                soweit keine abweichende Vereinbarung, gesetzliche Pflicht oder Sicherheitsausnahme greift.
              </p>
              <p className="mt-2">
                Anbieter: Anthropic PBC. Weitere Informationen findest du im{" "}
                <a
                  href="https://privacy.anthropic.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-(--accent-ink) hover:underline"
                >
                  Anthropic Privacy Center
                </a>
                .
              </p>
            </section>

            <section>
              <h2 className="font-semibold text-(--ink)">4. Sitzungen und Gesprächsverlauf</h2>
              <p className="mt-1">
                Für die technische Durchführung einer Beratung erzeugt SCENTAI eine zufällige Sitzungs-ID.
                Sie ist kein Kundenkonto und keine dauerhafte werbliche Nutzerkennung. Der Gesprächsverlauf
                kann für die Dauer dieser technischen Sitzung im Serverprozess vorgehalten werden. Für die
                zusammenhängende, pseudonymisierte Nutzungsstatistik beim Wechsel zwischen Beratung,
                Duftdetail und Vergleich erzeugt SCENTAI zusätzlich eine separate zufällige Analyse-Sitzungskennung.
                Diese kann für die Dauer der Browser-Sitzung im sessionStorage des jeweiligen Tabs gespeichert
                werden; die eigentliche technische Beratungs-Sitzungs-ID wird dafür nicht dauerhaft im Browser
                abgelegt. Eine dauerhafte persönliche Duft-Memory-Funktion ist im aktuellen MVP deaktiviert.
              </p>
            </section>

            <section>
              <h2 className="font-semibold text-(--ink)">5. Nutzungsstatistik und Händlerlinks</h2>
              <p className="mt-1">
                Für die interne Produktverbesserung erfasst SCENTAI im MVP eigene Nutzungsereignisse,
                zum Beispiel Seitenaufruf, Start einer Beratung, angezeigte Empfehlungen, Öffnen einer
                Produktansicht, Duftvergleiche, Katalogsuchen und Händler-Clickouts. Bei Katalogsuchen kann
                ein auf höchstens 80 Zeichen begrenzter normalisierter Suchbegriff zusammen mit der Trefferzahl
                gespeichert werden; E-Mail-artige Eingaben und lange nummernartige Eingaben werden hierfür
                verworfen. Zusätzlich können Produkt-ID, Vergleichsprodukt, Empfehlungsposition und die
                jeweilige SCENTAI-Oberfläche gespeichert werden. Beratungstexte, Namen, E-Mail-Adressen,
                IP-Adressen oder Browser-Fingerprints werden nicht in den Analyse-Datensatz geschrieben.
                Die technische Sitzungs-ID wird vor der Speicherung in einen verkürzten Einweg-Hash
                umgewandelt, damit Ereignisse innerhalb einer Sitzung zusammengefasst werden können, ohne
                die ursprüngliche Sitzungs-ID im Analyseprotokoll zu speichern.
              </p>
              <p className="mt-2">
                Die pseudonymisierten Analyseereignisse werden für die interne Auswertung in der von SCENTAI
                eingesetzten Supabase-Datenbankinfrastruktur gespeichert. Anbieter ist Supabase, Inc. Nach den
                veröffentlichten Datenschutzinformationen verarbeitet Supabase Kundendaten im Rahmen des
                Dienstes grundsätzlich als Auftragsverarbeiter. Weitere Informationen findest du in der{" "}
                <a
                  href="https://supabase.com/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-(--accent-ink) hover:underline"
                >
                  Datenschutzerklärung von Supabase
                </a>
                . Zusätzlich protokolliert SCENTAI beim Öffnen eines Händlerlinks einen Clickout-Datensatz mit
                Zeitpunkt, Angebot, Produkt, Händler, Netzwerk und der Information, ob ein Partnerlink verwendet
                wurde. Der eigentliche Kauf findet beim Händler statt. Auf dessen Website gelten anschließend
                die dortigen Datenschutz- und Trackingregeln. Partnerlinks werden bei SCENTAI entsprechend
                gekennzeichnet.
              </p>
            </section>

            <section>
              <h2 className="font-semibold text-(--ink)">6. Cookies und Tracking</h2>
              <p className="mt-1">
                SCENTAI setzt derzeit keine Google-Analytics-, Meta-Pixel- oder vergleichbaren externen
                Werbetracker ein und verwendet für die oben beschriebene interne Nutzungsstatistik keine
                dauerhafte werbliche Nutzerkennung. Sollten später zusätzliche Tracking-, Marketing- oder
                Drittanbieter-Analyseverfahren eingesetzt werden, wird diese Datenschutzerklärung angepasst
                und – soweit erforderlich – vorab eine Einwilligung eingeholt.
              </p>
            </section>

            <section>
              <h2 className="font-semibold text-(--ink)">7. Rechtsgrundlagen</h2>
              <p className="mt-1">
                Soweit die Verarbeitung erforderlich ist, um die von dir angeforderte SCENTAI-Beratung
                bereitzustellen, erfolgt sie auf Grundlage von Art. 6 Abs. 1 lit. b DSGVO. Technische
                Sicherheits-, Betriebs- und Missbrauchsschutzmaßnahmen sowie die datensparsame interne
                Auswertung pseudonymisierter Nutzungsereignisse und Händler-Clickouts stützen wir, soweit
                personenbezogene Daten betroffen sind und kein vorrangiges Einwilligungserfordernis besteht,
                auf unser berechtigtes Interesse an einem sicheren, funktionsfähigen und wirtschaftlich
                betreibbaren Dienst gemäß Art. 6 Abs. 1 lit. f DSGVO.
              </p>
            </section>

            <section>
              <h2 className="font-semibold text-(--ink)">8. Datenübermittlungen in Drittländer</h2>
              <p className="mt-1">
                Bei der Nutzung von Render, Anthropic und Supabase kann – abhängig vom jeweiligen Dienst,
                Projektstandort und Verarbeitungsvorgang – eine Verarbeitung außerhalb Deutschlands oder des
                Europäischen Wirtschaftsraums stattfinden. Soweit erforderlich, erfolgt eine solche Übermittlung
                auf Grundlage der jeweils anwendbaren datenschutzrechtlichen Garantien und Vereinbarungen der
                eingesetzten Dienstleister.
              </p>
            </section>

            <section>
              <h2 className="font-semibold text-(--ink)">9. Speicherdauer</h2>
              <p className="mt-1">
                Personenbezogene Daten werden nur so lange gespeichert, wie dies für den jeweiligen Zweck
                erforderlich ist oder gesetzliche Aufbewahrungspflichten bestehen. Technische Sitzungsdaten
                des MVP sind nicht als dauerhaftes Kundenkonto ausgelegt. Für Daten, die von externen
                Dienstleistern verarbeitet werden, gelten zusätzlich deren dokumentierte Aufbewahrungsfristen.
              </p>
            </section>

            <section>
              <h2 className="font-semibold text-(--ink)">10. Deine Rechte</h2>
              <p className="mt-1">
                Du hast im Rahmen der gesetzlichen Voraussetzungen insbesondere das Recht auf Auskunft,
                Berichtigung, Löschung, Einschränkung der Verarbeitung, Datenübertragbarkeit und Widerspruch.
                Außerdem kannst du dich bei einer zuständigen Datenschutzaufsichtsbehörde beschweren.
              </p>
              <p className="mt-2">
                Für Datenschutzanfragen kannst du uns unter{" "}
                {legal.email ? (
                  <a className="text-(--accent-ink) hover:underline" href={`mailto:${legal.email}`}>
                    {legal.email}
                  </a>
                ) : (
                  "der im Impressum genannten E-Mail-Adresse"
                )}{" "}
                kontaktieren.
              </p>
            </section>

            <section>
              <h2 className="font-semibold text-(--ink)">11. Änderungen dieser Datenschutzerklärung</h2>
              <p className="mt-1">
                Wir passen diese Datenschutzerklärung an, wenn sich Funktionen, Dienstleister oder die
                rechtlichen Rahmenbedingungen von SCENTAI ändern.
              </p>
            </section>
          </div>
        </article>

        <LegalFooter />
      </div>
    </main>
  );
}
