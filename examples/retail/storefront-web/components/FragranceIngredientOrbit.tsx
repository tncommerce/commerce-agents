import type { CSSProperties } from "react";

import NoteIcon from "@/components/NoteIcon";
import { noteLabel } from "@/lib/noteLabels";

type IngredientStyle = CSSProperties & {
  "--dufynd-ingredient-x": string;
  "--dufynd-ingredient-y": string;
  "--dufynd-ingredient-depth": string;
  "--dufynd-ingredient-delay": string;
};

const POSITIONS: Array<{
  x: string;
  y: string;
  depth: string;
  delay: string;
}> = [
  { x: "13%", y: "24%", depth: "0.92", delay: "0ms" },
  { x: "82%", y: "20%", depth: "1.04", delay: "900ms" },
  { x: "10%", y: "76%", depth: "1.00", delay: "1500ms" },
  { x: "84%", y: "72%", depth: "0.90", delay: "2300ms" },
];

export default function FragranceIngredientOrbit({
  notes,
}: {
  notes: string[];
}) {
  const uniqueNotes = Array.from(
    new Set(
      notes
        .map((note) => String(note || "").trim())
        .filter(Boolean),
    ),
  ).slice(0, POSITIONS.length);

  if (!uniqueNotes.length) return null;

  return (
    <div
      className="dufynd-fragrance-ingredient-orbit"
      aria-hidden
      data-dufynd-ingredient-count={uniqueNotes.length}
    >
      <div className="dufynd-fragrance-ingredient-ring dufynd-fragrance-ingredient-ring--outer" />
      <div className="dufynd-fragrance-ingredient-ring dufynd-fragrance-ingredient-ring--inner" />
      <div className="dufynd-fragrance-ingredient-trail" />

      {uniqueNotes.map((note, index) => {
        const position = POSITIONS[index];
        const style: IngredientStyle = {
          "--dufynd-ingredient-x": position.x,
          "--dufynd-ingredient-y": position.y,
          "--dufynd-ingredient-depth": position.depth,
          "--dufynd-ingredient-delay": position.delay,
        };

        return (
          <div
            key={note}
            className="dufynd-fragrance-ingredient"
            style={style}
            data-dufynd-fragrance-ingredient
          >
            <span className="dufynd-fragrance-ingredient-icon">
              <NoteIcon note={note} className="h-5 w-5" />
            </span>
            <span className="dufynd-fragrance-ingredient-label">
              {noteLabel(note)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
