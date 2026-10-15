"use client";

import { useEffect, useState } from "react";
import {
  measurementChoice, setMeasurementChoice, subscribeMeasurement,
  type MeasurementChoice,
} from "@/lib/measurementConsent";
import { initializeMeasurementPrivacy } from "@/lib/analytics";
import styles from "./MeasurementPreferences.module.css";

export default function MeasurementPreferences() {
  const [choice, setChoice] = useState<MeasurementChoice>("unknown");
  const [ready, setReady] = useState(false);
  const [editing, setEditing] = useState(false);
  useEffect(() => {
    const refresh = () => setChoice(measurementChoice());
    const unsubscribe = subscribeMeasurement(refresh);
    initializeMeasurementPrivacy(); refresh(); setReady(true);
    return unsubscribe;
  }, []);
  const choose = (next: "granted" | "denied") => {
    setMeasurementChoice(next);
    setEditing(false);
  };
  const visible = ready && (choice === "unknown" || editing);
  return (
    <>
      <section className={styles.footer} aria-label="Datenschutz-Einstellungen" data-measurement-choice={ready ? choice : "unknown"}>
        <span>Optionale DUFYND-Analyse: <strong>{choice === "granted" ? "an" : "aus"}</strong></span>
        <button type="button" className={styles.settings} onClick={() => setEditing(true)} aria-expanded={visible} aria-controls="dufynd-measurement-preferences">
          Datenschutz-Einstellungen
        </button>
        {choice === "granted" && (
          <button type="button" className={styles.settings} onClick={() => choose("denied")}>
            Analyse widerrufen
          </button>
        )}
      </section>
      {visible && (
        <section id="dufynd-measurement-preferences" className={styles.panel} aria-labelledby="dufynd-measurement-title" data-measurement-panel>
          <div className={styles.kicker}>Deine Entscheidung</div>
          <h2 id="dufynd-measurement-title">Düfte entdecken. Privatsphäre behalten.</h2>
          <p>Suche, Merkliste und Händlerangebote funktionieren ohne optionale Analyse. Mit deiner Zustimmung messen wir Seiten- und Produktaufrufe sowie Händlerweiterleitungen mit einer zufälligen Kennung und der Herkunft des Besuchs. Die Auswertung erfolgt für DUFYND über Supabase.</p>
          <p className={styles.detail}>Deine Auswahl bleibt auf diesem Gerät bis zu 180 Tage gespeichert. Du kannst sie unten über „Datenschutz-Einstellungen“ ändern oder die Analyse direkt widerrufen. Für den Kauf beim Händler gelten dessen Datenschutzregeln. <a href="/datenschutz">Mehr zum Datenschutz</a></p>
          <div className={styles.actions}>
            <button type="button" onClick={() => choose("denied")}>Nur notwendige Funktionen</button>
            <button type="button" onClick={() => choose("granted")}>Analyse erlauben</button>
          </div>
        </section>
      )}
    </>
  );
}
