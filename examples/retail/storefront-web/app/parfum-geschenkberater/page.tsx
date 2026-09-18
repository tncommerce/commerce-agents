import type { Metadata } from "next";

import AcquisitionLanding from "@/components/AcquisitionLanding";

export const metadata: Metadata = {
  title: "Parfum-Geschenkberater – Duft als Geschenk finden",
  description:
    "Finde mit SCENTAI ein Parfumgeschenk anhand von Person, Anlass, Budget und bekannten Duftvorlieben.",
  alternates: {
    canonical: "/parfum-geschenkberater",
  },
};

export default function ParfumGeschenkberaterPage() {
  return (
    <AcquisitionLanding
      analyticsSource="parfum_geschenkberater"
      eyebrow="Parfum verschenken"
      title="Ein Duftgeschenk wird leichter, wenn man zuerst die richtigen Fragen stellt."
      intro="Statt blind nach Bestsellern zu gehen, fragt SCENTAI nach Person, Budget, Anlass und bekannten Vorlieben. Daraus entsteht eine kleinere Auswahl, die du anschließend in Ruhe vergleichen kannst."
      primaryStart="gift"
      primaryLabel="Geschenkberatung starten"
      secondaryStarts={[
        {
          key: "date",
          label: "Elegante Abenddüfte ansehen",
        },
        {
          key: "signature",
          label: "Persönlichen Signature-Duft suchen",
        },
      ]}
      points={[
        {
          title: "Nicht nur nach Geschlecht",
          text: "Vorlieben, Stil, Anlass und bekannte Lieblingsdüfte sind oft hilfreicher als eine starre Einteilung in Damen- und Herrendüfte.",
        },
        {
          title: "Budget von Anfang an",
          text: "SCENTAI kann die Auswahl früh auf dein Budget begrenzen, statt dir erst danach unerreichbare Optionen zu zeigen.",
        },
        {
          title: "Auswahl nachvollziehen",
          text: "Du kannst sehen, warum ein Duft empfohlen wurde, Alternativen öffnen und Kandidaten direkt miteinander vergleichen.",
        },
      ]}
      trustNote="Beim Geschenkberater zählt die Passung zur beschenkten Person – nicht, welcher Händler oder welches Produkt die höchste Provision bringt."
    />
  );
}
