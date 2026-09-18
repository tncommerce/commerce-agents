// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

import LegalFooter from "@/components/LegalFooter";
import { legal, legalLocation, legalReady } from "@/lib/legal";

export const metadata = {
  title: "Impressum",
  description: "Anbieterkennzeichnung und Kontaktinformationen für SCENTAI.",
  alternates: {
    canonical: "/impressum",
  },
  robots: {
    index: false,
    follow: true,
  },
};

export default function ImpressumPage() {
  return (
    <main className="min-h-screen bg-(--ground) px-4 py-10 text-(--ink) sm:px-6">
      <div className="mx-auto max-w-3xl">
        <article className="rounded-2xl border border-(--line) bg-(--card) p-6 shadow-(--shadow-sm) sm:p-8">
          <a href="/" className="text-[13px] font-semibold text-(--accent-ink) hover:underline">
            ← Zurück zu SCENTAI
          </a>

          <h1 className="mt-5 text-3xl font-semibold tracking-[-0.03em]">Impressum</h1>
          <p className="mt-2 text-[13px] text-(--ink-soft)">Angaben gemäß § 5 DDG</p>

          {!legalReady ? (
            <div className="mt-5 rounded-xl border border-(--line) bg-(--well)/60 p-4 text-[13px] leading-6 text-(--ink-soft)">
              Die Impressumsangaben sind derzeit nicht vollständig geladen.
            </div>
          ) : null}

          <div className="mt-6 space-y-6 text-[15px] leading-7 text-(--ink-2)">
            <section>
              <h2 className="font-semibold text-(--ink)">Anbieter</h2>
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
              </p>
            </section>

            <section>
              <h2 className="font-semibold text-(--ink)">Kontakt</h2>
              <p className="mt-1">
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
              <h2 className="font-semibold text-(--ink)">Hinweis zum Angebot</h2>
              <p className="mt-1">
                SCENTAI ist ein digitaler Duftberatungs- und Empfehlungsdienst von {legal.businessName}.
                SCENTAI verkauft die dargestellten Produkte nicht selbst. Kaufverträge kommen ausschließlich
                zwischen dir und dem jeweils verlinkten Händler zustande.
              </p>
            </section>
          </div>
        </article>

        <LegalFooter />
      </div>
    </main>
  );
}
