"use client";

import type { CSSProperties } from "react";
import { useState } from "react";

import NoteIcon from "@/components/NoteIcon";
import { noteLabel } from "@/lib/noteLabels";

type NoteStage = "top" | "heart" | "base";

type ExplodedNote = {
  note: string;
  stage: NoteStage;
  index: number;
  x: string;
  y: string;
};

type NoteStyle = CSSProperties & {
  "--dufynd-note-x": string;
  "--dufynd-note-y": string;
  "--dufynd-note-delay": string;
};

const STAGE_LABELS: Record<NoteStage, string> = {
  top: "Kopf",
  heart: "Herz",
  base: "Basis",
};

const POSITIONS: Record<NoteStage, [string, string][]> = {
  top: [
    ["20%", "18%"],
    ["80%", "23%"],
    ["16%", "41%"],
  ],
  heart: [
    ["84%", "44%"],
    ["15%", "60%"],
    ["82%", "62%"],
  ],
  base: [
    ["24%", "82%"],
    ["50%", "88%"],
    ["76%", "82%"],
  ],
};

function uniqueNotes(notes: string[]): string[] {
  return [...new Set(notes.map((note) => note.trim()).filter(Boolean))];
}

function explodedNotes(
  top: string[],
  heart: string[],
  base: string[],
): ExplodedNote[] {
  const stages: [NoteStage, string[]][] = [
    ["top", uniqueNotes(top).slice(0, 3)],
    ["heart", uniqueNotes(heart).slice(0, 3)],
    ["base", uniqueNotes(base).slice(0, 3)],
  ];

  return stages.flatMap(([stage, notes]) =>
    notes.map((note, index) => ({
      note,
      stage,
      index,
      x: POSITIONS[stage][index][0],
      y: POSITIONS[stage][index][1],
    })),
  );
}

export default function FragranceExplodedNotes({
  cutoutUrl,
  alt,
  top,
  heart,
  base,
}: {
  cutoutUrl: string;
  alt: string;
  top: string[];
  heart: string[];
  base: string[];
}) {
  const [expanded, setExpanded] = useState(false);
  const notes = explodedNotes(top, heart, base);

  if (notes.length < 3) return null;

  return (
    <section
      className="dufynd-exploded-notes mt-5 overflow-hidden rounded-[26px] border border-(--line) bg-(--card) shadow-(--shadow-sm)"
      aria-labelledby="dufynd-exploded-heading"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-(--line) px-4 py-4 sm:px-5">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-(--accent-ink)">
            Verifizierte Produktdarstellung
          </div>
          <h2
            id="dufynd-exploded-heading"
            className="mt-1 text-[18px] font-semibold tracking-[-0.02em] text-(--ink)"
          >
            Duftaufbau in Bewegung
          </h2>
          <p className="mt-1 max-w-2xl text-[11.5px] leading-5 text-(--ink-soft)">
            Duftnoten lösen sich visuell in Kopf, Herz und Basis vom verifizierten
            Flakon. Die Darstellung erklärt das Duftprofil – nicht den physischen
            Flascheninhalt.
          </p>
        </div>

        <button
          type="button"
          aria-pressed={expanded}
          aria-controls="dufynd-exploded-stage"
          onClick={() => setExpanded((value) => !value)}
          className="rounded-xl border border-(--line-strong) bg-(--surface) px-3.5 py-2.5 text-[11.5px] font-semibold text-(--ink) shadow-sm transition hover:-translate-y-0.5 hover:border-(--ink)"
        >
          {expanded ? "Zusammenführen" : "Duftaufbau entfalten"}
        </button>
      </div>

      <div
        id="dufynd-exploded-stage"
        data-expanded={expanded ? "true" : "false"}
        className="dufynd-exploded-stage"
      >
        <div className="dufynd-exploded-halo" aria-hidden />
        <div className="dufynd-exploded-orbit dufynd-exploded-orbit--outer" aria-hidden />
        <div className="dufynd-exploded-orbit dufynd-exploded-orbit--inner" aria-hidden />

        <div className="dufynd-exploded-bottle">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={cutoutUrl} alt={alt} loading="lazy" decoding="async" />
        </div>

        {notes.map(({ note, stage, index, x, y }, noteIndex) => {
          const style: NoteStyle = {
            "--dufynd-note-x": x,
            "--dufynd-note-y": y,
            "--dufynd-note-delay": `${noteIndex * 34}ms`,
          };

          return (
            <div
              key={`${stage}:${note}`}
              data-dufynd-exploded-note
              data-stage={stage}
              data-index={index}
              className="dufynd-exploded-note"
              style={style}
            >
              <span className="dufynd-exploded-note-icon" aria-hidden>
                <NoteIcon note={note} className="h-4 w-4" />
              </span>
              <span className="min-w-0">
                <span className="block break-words text-[10.5px] font-semibold leading-[1.15] text-(--ink) sm:truncate">
                  {noteLabel(note)}
                </span>
                <span className="block text-[8.5px] font-semibold uppercase tracking-[0.08em] text-(--ink-soft)">
                  {STAGE_LABELS[stage]}
                </span>
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
