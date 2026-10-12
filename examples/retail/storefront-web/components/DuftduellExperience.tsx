"use client";

import { useState } from "react";
import AcquisitionInternalLink from "@/components/AcquisitionInternalLink";
import GuidedAdvisorLink from "@/components/GuidedAdvisorLink";
import {
  DUEL_ROUNDS,
  getDuelAdvisorPrompt,
  getDuelOutcome,
  type DuelChoice,
} from "@/lib/duftduell";

const TOTAL = DUEL_ROUNDS.length;

export default function DuftduellExperience() {
  const [answers, setAnswers] = useState<DuelChoice[]>([]);
  const [started, setStarted] = useState(false);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const index = answers.length;
  const finished = index === TOTAL;
  const result = finished ? getDuelOutcome(answers) : null;
  const active = !finished ? DUEL_ROUNDS[index] : null;

  function answer(choice: DuelChoice) {
    if (!started || finished) return;
    setAnswers((current) => (current.length === index ? [...current, choice] : current));
    setCopyState("idle");
  }

  function back() {
    setAnswers((current) => current.slice(0, -1));
    setCopyState("idle");
  }

  function reset() {
    setStarted(false);
    setAnswers([]);
    setCopyState("idle");
  }

  async function copyResult() {
    if (!result) return;
    const text = `Mein DUFYND Dufttyp: ${result.name}. ${result.kicker} Finde deinen auf https://dufynd.de/duftduell`;
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(text);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  }

  return (
    <div className="duel-shell">
      <header className="duel-topbar">
        <AcquisitionInternalLink href="/" className="duel-brand" aria-label="DUFYND Startseite">
          <img src="/icon.svg" alt="" aria-hidden="true" width={34} height={34} />
          <span>DUFYND</span>
        </AcquisitionInternalLink>
        <div className="duel-top-right"><span className="duel-live-dot" aria-hidden="true" /> ENTDECKEN. NICHT RATEN.</div>
        <AcquisitionInternalLink className="duel-exit" href="/duftfinder">Duftfinder <span aria-hidden="true">↗</span></AcquisitionInternalLink>
      </header>

      {!started ? (
        <main className="duel-intro" aria-labelledby="duel-heading">
          <div className="duel-intro-text">
            <span className="duel-kicker"><span className="duel-kicker-line" /> INTERAKTIVES DUFYND-ORIGINAL</span>
            <h1 id="duel-heading" className="duel-display">DUFT<span className="duel-display-dot">.</span><br /><em>DUELL</em><span className="duel-display-dot">.</span></h1>
            <p className="duel-intro-description">Vier Duelle. Zwei Optionen. Kein Duft-Fachchinesisch. Finde spielerisch heraus, welcher Duftstil dich mehr anspricht.</p>
            <button className="duel-start" onClick={() => setStarted(true)}>DUELL STARTEN <span aria-hidden="true">↗</span></button>
            <div className="duel-facts"><span>04 RUNDEN</span><span>2 ANTWORTEN PRO RUNDE</span><span>0 €</span></div>
          </div>
          <div className="duel-intro-stage" aria-hidden="true">
            <div className="duel-stage-grid" />
            <div className="duel-stage-orbit duel-stage-orbit-a" />
            <div className="duel-stage-orbit duel-stage-orbit-b" />
            <div className="duel-stage-disc">A<span>VS</span>B</div>
            <span className="duel-stage-sticker">DEIN STIL.<br />DEIN CALL.</span>
            <span className="duel-stage-issue">ISSUE N° 001</span>
          </div>
        </main>
      ) : (
        <main className="duel-play" aria-labelledby="duel-main-heading">
          <div className="duel-play-header">
            <div className="duel-counter">{finished ? "ERGEBNIS" : `ROUND ${String(index + 1).padStart(2, "0")}`} <span>/ {String(TOTAL).padStart(2, "0")}</span></div>
            <button className="duel-restart-mini" onClick={reset}>↺ Neustart</button>
          </div>
          <div className="duel-progress" aria-label={`${index} von ${TOTAL} Runden abgeschlossen`}>
            {DUEL_ROUNDS.map((step, stepIndex) => <span key={step.id} className={stepIndex < index ? "done" : stepIndex === index ? "current" : ""} />)}
          </div>

          {active ? (
            <div className="duel-round" key={active.id}>
              <div className="duel-round-title">
                <p className="duel-round-eyebrow">{active.eyebrow}</p>
                <h1 id="duel-main-heading">{active.question}</h1>
                <p>Nicht nachdenken. Dein erstes Gefühl zählt.</p>
              </div>
              <div className="duel-choice-grid">
                {active.options.map((item, optionIndex) => {
                  const side: DuelChoice = optionIndex === 0 ? "a" : "b";
                  return (
                    <button key={side} className={`duel-choice duel-choice-${side}`} onClick={() => answer(side)} aria-label={`${item.label} wählen: ${item.detail}`}>
                      <span className="duel-choice-top"><span>OPTION {side.toUpperCase()}</span><span aria-hidden="true">↗</span></span>
                      <span className="duel-choice-art" aria-hidden="true"><span className="duel-choice-art-main" /><span className="duel-choice-art-ring" /><span className="duel-choice-art-glint" /></span>
                      <span className="duel-choice-vibe">{item.vibe}</span>
                      <span className="duel-choice-label">{item.label}</span>
                      <span className="duel-choice-detail">{item.detail}</span>
                      <span className="duel-choice-select">DAS BIN ICH <span aria-hidden="true">→</span></span>
                    </button>
                  );
                })}
              </div>
              <div className="duel-round-bottom">
                <button className="duel-back" onClick={index === 0 ? reset : back}>{index === 0 ? "← Zurück zum Start" : "← Vorherige Frage"}</button>
                <span>01 + 01 = DEIN STIL</span>
              </div>
            </div>
          ) : result ? (
            <section className={`duel-result duel-result-${result.id}`} aria-labelledby="duel-main-heading">
              <div className="duel-result-copy">
                <div className="duel-result-eyebrow">DUFYND DUFT-DUELL · DEIN ERGEBNIS / {result.index}</div>
                <h1 id="duel-main-heading">{result.name}<span>.</span></h1>
                <strong>{result.kicker}</strong>
                <p>{result.description}</p>
                <div className="duel-tags" aria-label="Deine Stilvorlieben">{result.tags.map(tag=><span key={tag}>{tag}</span>)}</div>
                <div className="duel-result-actions">
                  <GuidedAdvisorLink
                    start="signature"
                    prompt={getDuelAdvisorPrompt(answers) || undefined}
                    className="duel-cta-primary"
                  >Passende Düfte finden <span aria-hidden="true">↗</span></GuidedAdvisorLink>
                  <button className="duel-cta-secondary" onClick={copyResult}>{copyState === "copied" ? "Kopiert ✓" : "Ergebnis kopieren ↗"}</button>
                </div>
                {copyState === "failed" ? <p className="duel-copy-error" role="status">Kopieren nicht verfügbar. Du kannst deinen Dufttyp oben ablesen.</p> : null}
                <button className="duel-result-repeat" onClick={reset}>↺ Noch einmal spielen</button>
              </div>
              <div className="duel-result-art" aria-hidden="true"><span>{result.index}</span><i>YOUR<br />SCENT<br />TYPE</i></div>
              <div className="duel-result-disclaimer">Das Duell ist eine spielerische Stil-Einordnung, keine objektive Duftmessung oder Produktempfehlung. Der DUFYND Advisor fragt nach deinem Budget und Anlass, bevor er passende Katalogdüfte prüft.</div>
            </section>
          ) : null}
        </main>
      )}

      <footer className="duel-footer">
        <span>© DUFYND · DEIN DUFT. DEINE ENTSCHEIDUNG.</span>
        <nav aria-label="Weitere Seiten">
          <AcquisitionInternalLink href="/duft">Katalog</AcquisitionInternalLink>
          <AcquisitionInternalLink href="/vergleich">Vergleiche</AcquisitionInternalLink>
          <AcquisitionInternalLink href="/transparenz">Transparenz</AcquisitionInternalLink>
          <AcquisitionInternalLink href="/impressum">Impressum</AcquisitionInternalLink>
        </nav>
      </footer>
    </div>
  );
}
