import type { Metadata } from "next";
import AcquisitionAnalytics from "@/components/AcquisitionAnalytics";
import DuftduellExperience from "@/components/DuftduellExperience";
import "./duftduell.css";

export const metadata: Metadata = {
  title: "Duft-Duell – Vier Entscheidungen, dein Duftstil",
  description: "Frisch oder warm? Understatement oder Statement? Finde in vier schnellen Duft-Duellen deinen Stil und starte die echte DUFYND Duftberatung.",
  alternates: { canonical: "/duftduell" },
  openGraph: {
    title: "DUFYND Duft-Duell – A oder B?",
    description: "Vier schnelle Duelle. Ein Duftstil. Du entscheidest.",
  },
};

export default function DuftDuellPage() {
  return (
    <>
      <AcquisitionAnalytics source="duftduell" />
      <DuftduellExperience />
    </>
  );
}
