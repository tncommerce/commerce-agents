// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

import LegalFooter from "@/components/LegalFooter";

export const metadata = {
  title: "Transparenz | SCENTAI",
  description: "Wie SCENTAI Empfehlungen, Händlerangebote und Partnerlinks behandelt.",
};

export default function TransparencyPage() {
  return (
    <main className="min-h-screen bg-(--ground) px-4 py-10 text-(--ink) sm:px-6">
      <div className="mx-auto max-w-3xl">
      <article className="rounded-2xl border border-(--line) bg-(--card) p-6 shadow-(--shadow-sm) sm:p-8">
        <a href="/" className="text-[13px] font-semibold text-(--accent-ink) hover:underline">
          ← Zurück zu SCENTAI
        </a>

        <h1 className="mt-5 text-3xl font-semibold tracking-[-0.03em]">
          Transparenz bei Empfehlungen und Händlerlinks
        </h1>

        <div className="mt-6 space-y-6 text-[15px] leading-7 text-(--ink-2)">
          <section>
            <h2 className="font-semibold text-(--ink)">Empfehlungen zuerst nach deinen Kriterien</h2>
            <p className="mt-1">
              SCENTAI bewertet Düfte anhand der verfügbaren Produktdaten und deiner Anfrage.
              Eine mögliche Partnerprovision soll nicht dazu führen, dass ein für dich schlechteres
              Produkt empfohlen wird.
            </p>
          </section>

          <section>
            <h2 className="font-semibold text-(--ink)">Wie Händlerangebote sortiert werden</h2>
            <p className="mt-1">
              Kaufbare Angebote werden unter anderem nach Verfügbarkeit, bekanntem Gesamtpreis
              inklusive Versand und Aktualität der Angebotsdaten bewertet. Nur wenn Angebote für
              den Kunden praktisch gleichwertig sind, kann eine höhere Partnerprovision als
              nachrangiger Tie-Breaker berücksichtigt werden.
            </p>
          </section>

          <section>
            <h2 className="font-semibold text-(--ink)">Partnerlinks</h2>
            <p className="mt-1">
              Bei entsprechend gekennzeichneten Partnerlinks kann SCENTAI eine Provision erhalten,
              wenn du beim Händler kaufst. Für dich soll sich der Händlerpreis dadurch nicht erhöhen.
              Kaufvertrag, Zahlung, Versand und Retouren erfolgen direkt über den jeweiligen Händler.
            </p>
          </section>

          <section>
            <h2 className="font-semibold text-(--ink)">Produkte ohne Partnerprogramm</h2>
            <p className="mt-1">
              Ein Duft kann weiterhin empfohlen und direkt zum Hersteller oder Händler verlinkt
              werden, auch wenn SCENTAI daran keine Provision verdient. Die beste passende Empfehlung
              soll nicht davon abhängen, ob ein Produkt monetarisierbar ist.
            </p>
          </section>

          <section>
            <h2 className="font-semibold text-(--ink)">Preise und Verfügbarkeit</h2>
            <p className="mt-1">
              Händlerpreise und Verfügbarkeit können sich ändern. SCENTAI kennzeichnet aktuelle
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
