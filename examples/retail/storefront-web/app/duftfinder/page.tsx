import type { Metadata } from "next";

import AcquisitionLanding from "@/components/AcquisitionLanding";

export const metadata: Metadata = {
  title: "Duftfinder – Parfum nach Anlass, Budget & Profil",
  description:
    "Finde mit DUFYND passende Parfums nach Anlass, Budget, Duftprofil und gewünschter Performance.",
  alternates: {
    canonical: "/duftfinder",
  },
};

export default function DuftfinderPage() {
  return (
    <AcquisitionLanding
      analyticsSource="duftfinder"
      eyebrow="DUFYND Duftfinder"
      title="Finde einen Duft, der zu dir und deinem Alltag passt."
      intro="Du musst keine Duftnoten auswendig kennen. Sag DUFYND, was du magst, wann du den Duft tragen willst und welches Budget du hast. Der Advisor grenzt das Sortiment anhand deiner Kriterien ein und erklärt die wichtigsten Unterschiede."
      primaryStart="signature"
      primaryLabel="Persönliche Beratung starten"
      secondaryStarts={[
        {
          key: "summer",
          label: "Frischen Sommerduft finden",
        },
        {
          key: "office",
          label: "Büroduft finden",
        },
        {
          key: "performance",
          label: "Starke Performance suchen",
        },
      ]}
      points={[
        {
          title: "Nach echten Kriterien",
          text: "Anlass, Budget, Duftprofil, Süße, Frische, Haltbarkeit und Ausstrahlung können gemeinsam berücksichtigt werden.",
        },
        {
          title: "Verständlich statt Fachchinesisch",
          text: "Du kannst einfach beschreiben, wie ein Duft wirken soll. DUFYND übersetzt das in vergleichbare Duft- und Performance-Daten.",
        },
        {
          title: "Danach direkt vergleichen",
          text: "Passende Kandidaten lassen sich auf Duftseiten und im Vergleich nebeneinander prüfen, bevor du einen Händler öffnest.",
        },
      ]}
      trustNote="Der Advisor soll zuerst den passenden Duft finden – auch dann, wenn DUFYND an diesem Produkt nichts verdient."
    />
  );
}
