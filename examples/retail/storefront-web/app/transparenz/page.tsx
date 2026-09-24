// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

import LegalFooter from "@/components/LegalFooter";

export const metadata = {
  title: "Transparenz",
  description: "Wie DUFYND Empfehlungen, Händlerangebote und Partnerlinks behandelt.",
  alternates: {
    canonical: "/transparenz",
  },
};

export default function TransparencyPage() {
  return (
    <main className="min-h-screen bg-(--ground) px-4 py-10 text-(--ink) sm:px-6">
      <div className="mx-auto max-w-3xl">
      <article className="rounded-2xl border border-(--line) bg-(--card) p-6 shadow-(--shadow-sm) sm:p-8">
        <a href="/" className="text-[13px] font-semibold text-(--accent-ink) hover:underline">
          ← Zurück zu DUFYND
        </a>

        <h1 className="mt-5 text-3xl font-semibold tracking-[-0.03em]">
          Transparenz bei Empfehlungen und Händlerlinks
        </h1>

        <div className="mt-6 space-y-6 text-[15px] leading-7 text-(--ink-2)">
          <section>
            <h2 className="font-semibold text-(--ink)">Empfehlungen zuerst nach deinen Kriterien</h2>
            <p className="mt-1">
              DUFYND bewertet Düfte anhand der verfügbaren Produktdaten und deiner Anfrage.
              Eine mögliche Partnerprovision hat keinen Einfluss auf die Produktempfehlung.
            </p>
          </section>

          <section>
            <h2 className="font-semibold text-(--ink)">Wie Händlerangebote sortiert werden</h2>
            <p className="mt-1">
              Kaufbare Angebote werden unter anderem nach Verfügbarkeit, bekanntem Gesamtpreis
              inklusive Versand und Aktualität der Angebotsdaten bewertet. Eine mögliche
              Partnerprovision hat keinen Einfluss auf die Reihenfolge der Händlerangebote.
            </p>
          </section>

          <section>
            <h2 className="font-semibold text-(--ink)">Partnerangebote und weitere Kaufoptionen</h2>
            <p className="mt-1">
              In den Händlerangeboten unterscheidet DUFYND sichtbar zwischen
              <strong> Partnerangeboten</strong> und <strong>weiteren Kaufoptionen</strong>.
              Bei Partnerangeboten kann DUFYND eine Provision erhalten, wenn du
              beim Händler kaufst. Weitere Kaufoptionen zeigen wir auch dann,
              wenn aktuell keine Vergütung an DUFYND erfolgt.
            </p>
            <p className="mt-2">
              Der Beratungswert steht dabei vor der Monetarisierung: Ein sinnvoller
              Händler- oder Herstellerlink kann deshalb auch ohne Partnerprogramm
              angezeigt werden. Eine mögliche Provision hat keinen Einfluss auf die
              Reihenfolge der Händlerangebote.
            </p>
          </section>

          <section>
            <h2 className="font-semibold text-(--ink)">
              Direkte Einstiege zu Partnerhändlern
            </h2>
            <p className="mt-1">
              DUFYND kann zusätzlich allgemeine Partnerlinks zu einem Händler
              anbieten, wenn du dort ohnehin weiterstöbern möchtest. Dabei ist
              der Einstieg nicht an den zuvor empfohlenen Duft gebunden. Ob
              und welche spätere Bestellung DUFYND zugerechnet und vergütet
              wird, richtet sich nach den jeweiligen Bedingungen und
              Attributionsregeln des Partnerprogramms. Auch diese
              Händler-Einstiege verändern niemals die Reihenfolge der
              Duftempfehlungen.
            </p>
          </section>

          <section>
            <h2 className="font-semibold text-(--ink)">Produkte ohne Partnerprogramm</h2>
            <p className="mt-1">
              Ein Duft kann weiterhin empfohlen und direkt zum Hersteller oder Händler verlinkt
              werden, auch wenn DUFYND daran keine Provision verdient. Die beste passende Empfehlung
              soll nicht davon abhängen, ob ein Produkt monetarisierbar ist.
            </p>
          </section>

          <section>
            <h2 className="font-semibold text-(--ink)">
              Merkliste und Sammlungsprofil
            </h2>
            <p className="mt-1">
              Merkliste und Duftsammlung werden lokal im Browser gespeichert.
              Das Sammlungsprofil fasst ausschließlich vorhandene DUFYND-
              Profilwerte der von dir markierten Düfte zusammen. Hinweise auf
              mögliche Profil-Ergänzungen bedeuten nicht, dass deine Sammlung
              unvollständig ist oder dass du weitere Düfte kaufen solltest.
            </p>
            <p className="mt-2">
              Deine Sammlung beeinflusst den Advisor nicht automatisch. Erst
              wenn du ausdrücklich die sammlungsbasierte Beratung startest,
              wird eine kompakte Zusammenfassung für diese Beratung übergeben.
              Besitz wird dabei nicht automatisch als Vorliebe interpretiert,
              und bereits vorhandene Düfte sollen nicht als neuer Kauf
              empfohlen werden.
            </p>
          </section>

          <section>
            <h2 className="font-semibold text-(--ink)">Preise und Verfügbarkeit</h2>
            <p className="mt-1">
              Händlerpreise und Verfügbarkeit können sich ändern. DUFYND kennzeichnet aktuelle
              Händlerangebote getrennt von ungefähren Marktpreis-Orientierungen und verwirft
              veraltete Angebotsdaten aus der aktiven Händlerauswahl.
            </p>
          </section>
        </div>
      </article>
      <LegalFooter />
      </div>
    </main>
  );
}
