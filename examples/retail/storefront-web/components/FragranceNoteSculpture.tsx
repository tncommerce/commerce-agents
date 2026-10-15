"use client";

import { useEffect, useId, useRef, useState } from "react";
import { noteLabel } from "@/lib/noteLabels";
import styles from "./FragranceNoteSculpture.module.css";

type Notes = {
  top: string[];
  heart: string[];
  base: string[];
  key: string[];
  supporting: string[];
};
type Renderer = {
  update(angle: number, selected: number): void;
  dispose(): void;
};

export default function FragranceNoteSculpture({ notes }: { notes: Notes }) {
  const heading = useId();
  const hasPyramid = [...notes.top, ...notes.heart, ...notes.base].length > 0;
  const groups = hasPyramid
    ? [
        {
          label: "Kopf",
          notes: notes.top,
          description: "Der erste Eindruck des Dufts.",
        },
        {
          label: "Herz",
          notes: notes.heart,
          description: "Der Charakter im Zentrum des Duftprofils.",
        },
        {
          label: "Basis",
          notes: notes.base,
          description: "Die Basis des Duftprofils.",
        },
      ]
    : [
        {
          label: "Schlüsselnoten",
          notes: notes.key,
          description:
            "Dokumentierte prägende Noten. Eine zeitliche Duftentwicklung ist nicht ausgewiesen.",
        },
        {
          label: "Weitere Noten",
          notes: notes.supporting,
          description: "Ergänzende dokumentierte Noten dieses Dufts.",
        },
      ];
  const [selected, setSelected] = useState(() =>
    Math.max(
      0,
      groups.findIndex((group) => group.notes.length > 0),
    ),
  );
  const [eligible, setEligible] = useState(false);
  const [active, setActive] = useState(false);
  const [failed, setFailed] = useState(false);
  const [angle, setAngle] = useState(0.25);
  const latest = useRef({ angle, selected });
  latest.current = { angle, selected };
  const canvas = useRef<HTMLCanvasElement>(null);
  const renderer = useRef<Renderer | null>(null);
  const drag = useRef<{ x: number; angle: number } | null>(null);
  const counts = groups.map((group) => group.notes.length).join(",");
  useEffect(() => {
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const navigatorHints = navigator as Navigator & {
      deviceMemory?: number;
      connection?: { saveData?: boolean };
    };
    const refresh = () => {
      const supported =
        !motion.matches &&
        !navigatorHints.connection?.saveData &&
        (navigatorHints.deviceMemory ?? 8) >= 4 &&
        (navigator.hardwareConcurrency || 4) >= 4;
      setEligible(supported);
      if (!supported) setActive(false);
    };
    refresh();
    motion.addEventListener("change", refresh);
    return () => motion.removeEventListener("change", refresh);
  }, []);
  useEffect(() => {
    if (!active || !eligible || !canvas.current) return;
    let cancelled = false;
    void import("@/lib/noteSculptureRenderer")
      .then(({ createNoteSculptureRenderer }) => {
        if (cancelled || !canvas.current) return;
        try {
          renderer.current = createNoteSculptureRenderer(
            canvas.current,
            counts.split(",").map(Number),
            () => {
              setFailed(true);
              setActive(false);
            },
          );
          renderer.current.update(
            latest.current.angle,
            latest.current.selected,
          );
        } catch {
          setFailed(true);
          setActive(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFailed(true);
          setActive(false);
        }
      });
    return () => {
      cancelled = true;
      renderer.current?.dispose();
      renderer.current = null;
    };
    // Orientation and focus update independently, without rebuilding the context.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, eligible, counts]);
  useEffect(() => {
    renderer.current?.update(angle, selected);
  }, [angle, selected]);
  if (!groups.some((group) => group.notes.length)) return null;
  const current = groups[selected] || groups[0];
  return (
    <section
      className={styles.section}
      aria-labelledby={heading}
      data-note-sculpture
      data-note-view={active ? "3d" : "static"}
    >
      <div className={styles.heading}>
        <p>Duftstudio</p>
        <h2 id={heading}>Noten im Raum</h2>
        <span>
          Erkunde die dokumentierten Noten. Die Formen sind eine abstrakte
          Darstellung.
        </span>
      </div>
      <div className={styles.layout}>
        <div className={styles.stage}>
          {active ? (
            <canvas
              ref={canvas}
              className={styles.canvas}
              aria-hidden="true"
              onPointerDown={(event) => {
                if (event.button !== 0) return;
                drag.current = { x: event.clientX, angle };
                event.currentTarget.setPointerCapture(event.pointerId);
              }}
              onPointerMove={(event) => {
                if (drag.current)
                  setAngle(
                    drag.current.angle + (event.clientX - drag.current.x) / 100,
                  );
              }}
              onPointerUp={() => {
                drag.current = null;
              }}
              onPointerCancel={() => {
                drag.current = null;
              }}
              onLostPointerCapture={() => {
                drag.current = null;
              }}
            />
          ) : (
            <svg
              className={styles.static}
              viewBox="0 0 360 270"
              aria-hidden="true"
            >
              {groups.map((group, layer) => (
                <g key={group.label} opacity={selected === layer ? 1 : 0.35}>
                  <ellipse
                    cx="180"
                    cy={65 + layer * 70}
                    rx="103"
                    ry="25"
                    fill="none"
                    stroke={["#6e9061", "#b67c74", "#987847"][layer]}
                    strokeWidth="1"
                  />
                  {group.notes.slice(0, 12).map((note, index, list) => (
                    <circle
                      key={`${note}-${index}`}
                      cx={
                        180 +
                        Math.cos((index / list.length) * Math.PI * 2) * 103
                      }
                      cy={
                        65 +
                        layer * 70 +
                        Math.sin((index / list.length) * Math.PI * 2) * 25
                      }
                      r="15"
                      fill={["#8aa478", "#bf8c80", "#ac9067"][layer]}
                    />
                  ))}
                </g>
              ))}
            </svg>
          )}
          <div className={styles.controls}>
            {eligible && !failed ? (
              <button
                type="button"
                onClick={() => setActive(!active)}
                aria-pressed={active}
              >
                {active ? "Statische Ansicht" : "Raumansicht öffnen"}
              </button>
            ) : (
              <span>
                {failed
                  ? "Statische Ansicht · 3D nicht verfügbar"
                  : "Statische Ansicht"}
              </span>
            )}
            {active ? (
              <>
                <button
                  type="button"
                  onClick={() => setAngle(angle - 0.35)}
                  aria-label="Noten nach links drehen"
                >
                  ↶
                </button>
                <button
                  type="button"
                  onClick={() => setAngle(angle + 0.35)}
                  aria-label="Noten nach rechts drehen"
                >
                  ↷
                </button>
              </>
            ) : null}
          </div>
        </div>
        <div className={styles.detail}>
          <div className={styles.tabs} aria-label="Notengruppe auswählen">
            {groups.map((group, index) => (
              <button
                key={group.label}
                type="button"
                disabled={!group.notes.length}
                aria-pressed={selected === index}
                onClick={() => setSelected(index)}
              >
                {group.label}
              </button>
            ))}
          </div>
          <div aria-live="polite" aria-atomic="true">
            <h3>{current.label}</h3>
            <p>{current.description}</p>
            <ul>
              {current.notes.map((note, index) => (
                <li key={`${note}-${index}`}>{noteLabel(note)}</li>
              ))}
            </ul>
          </div>
          <small>
            Die Anordnung zeigt keine Mengenverhältnisse und keine
            Molekülstruktur.
          </small>
        </div>
      </div>
    </section>
  );
}
