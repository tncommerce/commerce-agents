import type { Metadata } from "next";

import AcquisitionLanding from "@/components/AcquisitionLanding";

export const metadata: Metadata = {
  title: "Parfum-Alternativen finden & vergleichen",
  description:
    "Finde mit DUFYND Parfum-Alternativen und vergleiche Duftrichtung, Performance, Community-Daten und Preis.",
  alternates: {
    canonical: "/parfum-alternativen",
  },
};

export default function ParfumAlternativenPage() {
  return (
    <AcquisitionLanding
      analyticsSource="parfum_alternativen"
      eyebrow="Original & Alternative"
      title="Finde eine Alternative, ohne so zu tun, als wäre jeder Duft ein 1:1-Klon."
      intro="DUFYND trennt enge Duftbeziehungen, inspirierte Düfte und weiter gefasste Alternativen. Dadurch kannst du Preis, Duftrichtung und Performance vergleichen, ohne Unterschiede zu verschweigen."
      primaryStart="alternative"
      primaryLabel="Alternative zu einem Duft finden"
      secondaryStarts={[
        {
          key: "performance",
          label: "Alternative mit starker Performance",
        },
        {
          key: "signature",
          label: "Anderen passenden Duft finden",
        },
      ]}
      points={[
        {
          title: "Beziehungen statt Behauptungen",
          text: "DUFYND nutzt dokumentierte Duftbeziehungen und kennzeichnet, ob zwei Düfte sehr nah, inspiriert oder nur stilistisch verwandt sind.",
        },
        {
          title: "Preis ist nur ein Teil",
          text: "Eine günstigere Alternative ist nicht automatisch besser. Profil, Haltbarkeit, Ausstrahlung und dein Anlass bleiben Teil der Entscheidung.",
        },
        {
          title: "Original bleibt eine Option",
          text: "Wenn das Original besser zu deiner Anfrage passt, darf es weiterhin empfohlen werden – unabhängig davon, ob eine Alternative provisioniert wird.",
        },
      ]}
      trustNote="Eine Alternative wird nicht bevorzugt, nur weil sie günstiger ist oder eine höhere Partnervergütung verspricht."
    />
  );
}
