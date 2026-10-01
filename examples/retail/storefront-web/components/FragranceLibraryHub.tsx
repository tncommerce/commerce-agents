"use client";

import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";

import FragranceSaveControls from "@/components/FragranceSaveControls";
import FragranceVisual from "@/components/FragranceVisual";
import GuidedAdvisorLink from "@/components/GuidedAdvisorLink";
import { accordLabel } from "@/lib/accordLabels";
import {
  clearFragranceLibrary,
  FRAGRANCE_LIBRARY_EVENT,
  FRAGRANCE_LIBRARY_STORAGE_KEY,
  parseFragranceLibraryBackup,
  readFragranceLibrary,
  replaceFragranceLibrary,
  type FragranceLibraryState,
} from "@/lib/fragranceLibrary";
import {
  isVerifiedProductTruthVisual,
  visualWorldFor,
  type StaticFragrance,
} from "@/lib/fragranceCatalog";

type LibraryMode = "wishlist" | "owned";

const PROFILE_AXES = [
  {
    key: "freshness",
    label: "Frische",
  },
  {
    key: "sweetness",
    label: "Süße",
  },
  {
    key: "woodiness",
    label: "Holzigkeit",
  },
  {
    key: "spiciness",
    label: "Würze",
  },
] as const;

function dominantLibraryProfile(
  fragrance: StaticFragrance,
): {
  key: (typeof PROFILE_AXES)[number]["key"];
  label: string;
  value: number;
} | null {
  const ranked = PROFILE_AXES.map((axis) => ({
    key: axis.key,
    label: axis.label,
    value: Math.max(
      0,
      Math.min(10, fragrance.scores[axis.key] ?? 0),
    ),
  })).sort(
    (a, b) =>
      b.value - a.value ||
      a.label.localeCompare(b.label, "de"),
  );

  return ranked[0]?.value > 0 ? ranked[0] : null;
}

function emptyState(): FragranceLibraryState {
  return {
    version: 1,
    wishlist: [],
    owned: [],
  };
}

function average(values: number[]): number | null {
  if (!values.length) return null;

  return (
    values.reduce((sum, value) => sum + value, 0) /
    values.length
  );
}

function formatOneDecimal(value: number | null): string {
  return value == null
    ? "–"
    : value.toLocaleString("de-DE", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      });
}

function collectionProfile(
  owned: StaticFragrance[],
  all: StaticFragrance[],
) {
  const axisStats = PROFILE_AXES.map((axis) => {
    const values = owned
      .map((fragrance) => fragrance.scores[axis.key])
      .filter(
        (value): value is number => value != null,
      );

    return {
      ...axis,
      average: average(values),
      strongCount: values.filter(
        (value) => value >= 7,
      ).length,
    };
  });

  const accordCounts = new Map<string, number>();
  for (const fragrance of owned) {
    for (const accord of new Set(fragrance.accords)) {
      accordCounts.set(
        accord,
        (accordCounts.get(accord) || 0) + 1,
      );
    }
  }

  const topAccords = [...accordCounts.entries()]
    .sort(
      (a, b) =>
        b[1] - a[1] ||
        a[0].localeCompare(b[0], "de"),
    )
    .slice(0, 6)
    .map(([accord, count]) => ({
      accord,
      count,
    }));

  const ownedIds = new Set(
    owned.map((fragrance) => fragrance.product_id),
  );
  const missingAxes = axisStats.filter(
    (axis) => axis.strongCount === 0,
  );
  const suggestions: {
    fragrance: StaticFragrance;
    reason: string;
  }[] = [];
  const seen = new Set<string>();

  for (const axis of missingAxes) {
    const candidate = [...all]
      .filter(
        (fragrance) =>
          !ownedIds.has(fragrance.product_id) &&
          !seen.has(fragrance.product_id) &&
          (fragrance.scores[axis.key] ?? 0) >= 7,
      )
      .sort(
        (a, b) =>
          b.community.rating_count -
            a.community.rating_count ||
          (b.community.rating_10 ?? 0) -
            (a.community.rating_10 ?? 0),
      )[0];

    if (!candidate) continue;

    seen.add(candidate.product_id);
    suggestions.push({
      fragrance: candidate,
      reason: `Deutlich ${axis.label.toLowerCase()} im DUFYND-Profil`,
    });
  }

  return {
    axisStats,
    topAccords,
    missingAxes,
    suggestions: suggestions.slice(0, 4),
  };
}

function collectionAdvisorPrompt(
  owned: StaticFragrance[],
  profile: ReturnType<typeof collectionProfile>,
): string {
  const fragranceList = owned
    .slice(0, 40)
    .map(
      (fragrance) =>
        `${fragrance.brand} ${fragrance.name}`,
    )
    .join("; ");

  const axisSummary = profile.axisStats
    .map(
      (axis) =>
        `${axis.label} Ø ${formatOneDecimal(axis.average)}/10`,
    )
    .join(", ");

  const accordSummary = profile.topAccords
    .slice(0, 5)
    .map((item) => accordLabel(item.accord))
    .join(", ");

  const omitted =
    owned.length > 40
      ? ` Weitere ${owned.length - 40} gespeicherte Düfte sind in dieser kompakten Übergabe nicht einzeln aufgeführt.`
      : "";

  return [
    "Ich möchte ausdrücklich, dass du meine aktuelle DUFYND-Duftsammlung nur für diese Beratung berücksichtigst.",
    `Ich besitze aktuell: ${fragranceList}.${omitted}`,
    `Das grobe DUFYND-Sammlungsprofil lautet: ${axisSummary}.`,
    accordSummary
      ? `Häufige Akkorde in der Sammlung: ${accordSummary}.`
      : "",
    "Leite aus dem Besitz dieser Düfte nicht automatisch persönliche Vorlieben ab und behandle die Sammlung nicht als dauerhafte Erinnerung.",
    "Empfiehl keinen bereits genannten Duft als neuen Kauf.",
    "Hilf mir stattdessen, bewusst eine sinnvolle Ergänzung oder einen anderen Einsatzzweck zu finden.",
    "Frage mich zuerst kurz nach Anlass, Budget und danach, welche Art von Ergänzung ich suche, bevor du konkrete Empfehlungen gibst.",
  ]
    .filter(Boolean)
    .join(" ");
}

function FragranceCard({
  fragrance,
  source,
}: {
  fragrance: StaticFragrance;
  source: string;
}) {
  const visual =
    fragrance.presentation_visual ||
    fragrance.preferred_visual;
  const isProductTruth = isVerifiedProductTruthVisual(visual);
  const dominantProfile = dominantLibraryProfile(fragrance);

  return (
    <article
      className="dufynd-library-card overflow-hidden rounded-2xl border border-(--line) bg-(--card) shadow-(--shadow-sm)"
      data-dufynd-library-theme={
        dominantProfile?.key || "balanced"
      }
    >
      <a
        href={`/duft/${fragrance.slug}`}
        className="group block"
      >
        <div
          className="dufynd-library-card-stage"
          data-dufynd-library-card-stage
        >
          <div
            aria-hidden
            className="dufynd-library-card-atmosphere"
          />
          <FragranceVisual
            imageUrl={visual?.url}
            cutoutUrl={isProductTruth ? visual?.url : undefined}
            backdropUrl={
              isProductTruth ? fragrance.backdrop_visual?.url : undefined
            }
            alt={`${fragrance.brand} ${fragrance.name}`}
            variant="card"
            mode={isProductTruth ? "cutout" : "editorial"}
            world={visualWorldFor(fragrance)}
            className="dufynd-library-card-visual h-48 w-full"
          />
          {dominantProfile ? (
            <div className="dufynd-library-card-signature">
              <span>{dominantProfile.label}</span>
              <strong>{dominantProfile.value}/10</strong>
            </div>
          ) : null}
        </div>

        <div className="dufynd-library-card-body p-4 pb-3">
          <div className="text-[10.5px] font-medium uppercase tracking-[0.08em] text-(--ink-soft)">
            {fragrance.brand}
          </div>
          <h2 className="mt-1 text-[16px] font-semibold leading-5">
            {fragrance.name}
          </h2>
          <div className="mt-2 text-[11px] text-(--ink-soft)">
            {fragrance.concentration} ·{" "}
            {fragrance.volume_ml} ml
            {fragrance.community.rating_10 != null
              ? ` · ${formatOneDecimal(
                  fragrance.community.rating_10,
                )}/10${fragrance.community.provisional ? " · vorläufig" : ""}`
              : ""}
          </div>
        </div>
      </a>

      <div className="dufynd-library-card-actions flex flex-wrap items-center justify-between gap-2 border-t border-(--line) p-3">
        <FragranceSaveControls
          productId={fragrance.product_id}
          source={source}
          compact
        />
        <a
          href={`/vergleich?left=${encodeURIComponent(fragrance.product_id)}`}
          aria-label={`${fragrance.brand} ${fragrance.name} mit einem anderen Duft vergleichen`}
          className="rounded-lg px-2 py-1.5 text-[11px] font-semibold text-(--accent-ink) transition hover:bg-(--well)"
        >
          Vergleichen →
        </a>
      </div>
    </article>
  );
}

export default function FragranceLibraryHub({
  mode,
  fragrances,
}: {
  mode: LibraryMode;
  fragrances: StaticFragrance[];
}) {
  const [library, setLibrary] =
    useState<FragranceLibraryState>(emptyState());
  const [ready, setReady] = useState(false);
  const [backupStatus, setBackupStatus] = useState("");
  const importInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const sync = () => {
      setLibrary(readFragranceLibrary());
      setReady(true);
    };
    const handleStorage = (event: StorageEvent) => {
      if (
        event.key === FRAGRANCE_LIBRARY_STORAGE_KEY ||
        event.key === null
      ) {
        sync();
      }
    };

    sync();
    window.addEventListener(
      FRAGRANCE_LIBRARY_EVENT,
      sync,
    );
    window.addEventListener("storage", handleStorage);

    return () => {
      window.removeEventListener(
        FRAGRANCE_LIBRARY_EVENT,
        sync,
      );
      window.removeEventListener(
        "storage",
        handleStorage,
      );
    };
  }, []);

  const byId = useMemo(
    () =>
      new Map(
        fragrances.map((fragrance) => [
          fragrance.product_id,
          fragrance,
        ]),
      ),
    [fragrances],
  );

  const activeIds =
    mode === "wishlist"
      ? library.wishlist
      : library.owned;
  const active = activeIds
    .map((productId) => byId.get(productId))
    .filter(
      (fragrance): fragrance is StaticFragrance =>
        Boolean(fragrance),
    );

  const owned = library.owned
    .map((productId) => byId.get(productId))
    .filter(
      (fragrance): fragrance is StaticFragrance =>
        Boolean(fragrance),
    );

  const profile = useMemo(
    () => collectionProfile(owned, fragrances),
    [fragrances, owned],
  );

  const title =
    mode === "wishlist"
      ? "Meine Merkliste"
      : "Meine Duftsammlung";
  const intro =
    mode === "wishlist"
      ? "Speichere interessante Düfte für später und verschiebe sie mit einem Klick in deine Sammlung."
      : "Behalte deine DUFYND-Düfte im Blick und erkenne grobe Profil-Schwerpunkte deiner Sammlung.";
  const emptyTitle =
    mode === "wishlist"
      ? "Noch nichts gemerkt"
      : "Deine Sammlung ist noch leer";
  const emptyText =
    mode === "wishlist"
      ? "Öffne einen Duft und tippe auf „Merken“. Deine Auswahl bleibt nur in diesem Browser gespeichert."
      : "Öffne einen Duft und markiere ihn als Teil deiner Sammlung. Es wird kein Kundenkonto benötigt.";

  const exportBackup = () => {
    const file = new Blob([JSON.stringify(library, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(file);
    const link = document.createElement("a");
    link.href = url;
    link.download = `dufynd-duftliste-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
    setBackupStatus("Sicherung heruntergeladen. Bewahre die Datei selbst sicher auf.");
  };

  const importBackup = async (event: ChangeEvent<HTMLInputElement>) => {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file) return;

    try {
      if (file.size > 128 * 1024) throw new Error("file too large");
      const next = parseFragranceLibraryBackup(JSON.parse(await file.text()));
      if (!next) throw new Error("invalid backup");

      const currentLibrary = readFragranceLibrary();
      const replacing = currentLibrary.wishlist.length + currentLibrary.owned.length > 0;
      if (
        replacing &&
        !window.confirm(
          "Diese Sicherung ersetzt deine aktuelle Merkliste und Sammlung auf diesem Gerät. Fortfahren?",
        )
      ) {
        setBackupStatus("Import abgebrochen. Deine aktuelle Auswahl bleibt erhalten.");
        return;
      }

      if (!replaceFragranceLibrary(next)) throw new Error("storage unavailable");
      setLibrary(next);
      setBackupStatus(
        `Sicherung geladen: ${next.wishlist.length} gemerkt, ${next.owned.length} in Sammlung.`,
      );
    } catch {
      setBackupStatus("Import fehlgeschlagen. Bitte wähle eine gültige DUFYND-Sicherungsdatei.");
    } finally {
      input.value = "";
    }
  };

  if (!ready) {
    return (
      <div
        className="mt-6 rounded-2xl border border-(--line) bg-(--card) p-5 text-[13px] text-(--ink-soft)"
        aria-busy="true"
      >
        Persönliche Duftliste wird geladen …
      </div>
    );
  }

  return (
    <>
      <section className="dufynd-library-hero relative mt-6 overflow-hidden rounded-[30px] border border-[#d9bd82]/25 bg-[#15120f] p-5 text-white shadow-[0_26px_80px_-42px_rgba(45,29,8,0.95)] sm:p-7">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_10%,rgba(217,189,130,0.18),transparent_32%),radial-gradient(circle_at_88%_78%,rgba(111,74,32,0.24),transparent_34%),linear-gradient(135deg,#19140f_0%,#0d0b09_58%,#20170d_100%)]"
        />
        <div className="relative flex flex-wrap items-start justify-between gap-5">
          <div className="max-w-2xl">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.16em] text-[#d9bd82]">
              Persönlich · lokal gespeichert
            </div>
            <h1 className="mt-2 text-[30px] font-semibold tracking-[-0.04em] text-[#fffaf0] sm:text-[42px]">
              {title}
            </h1>
            <p className="mt-3 max-w-xl text-[13.5px] leading-6 text-white/68">
              {intro}
            </p>
            <div
              className="mt-5 flex flex-wrap gap-2"
              aria-label="Persönliche Duftübersicht"
            >
              <span className="rounded-full border border-white/12 bg-white/[0.055] px-3 py-1.5 text-[10.5px] font-semibold text-white/75">
                {library.owned.length} in Sammlung
              </span>
              <span className="rounded-full border border-white/12 bg-white/[0.055] px-3 py-1.5 text-[10.5px] font-semibold text-white/75">
                {library.wishlist.length} auf Merkliste
              </span>
              <span className="rounded-full border border-[#d9bd82]/25 bg-[#d9bd82]/10 px-3 py-1.5 text-[10.5px] font-semibold text-[#e8cf9d]">
                Nur auf diesem Gerät
              </span>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {mode === "owned" && owned.length ? (
              <GuidedAdvisorLink
                start="collection"
                prompt={collectionAdvisorPrompt(
                  owned,
                  profile,
                )}
                className="rounded-xl bg-[#d9bd82] px-3 py-2 text-[12px] font-semibold text-[#21170b] transition hover:brightness-105"
              >
                Mit meiner Sammlung beraten lassen
              </GuidedAdvisorLink>
            ) : null}
            <a
              href={
                mode === "wishlist"
                  ? "/sammlung"
                  : "/merkliste"
              }
              className="rounded-xl border border-white/15 bg-white/[0.055] px-3 py-2 text-[12px] font-semibold text-white/85 transition hover:border-[#d9bd82]/45 hover:bg-white/[0.08]"
            >
              {mode === "wishlist"
                ? `Sammlung (${library.owned.length})`
                : `Merkliste (${library.wishlist.length})`}
            </a>
            <a
              href="/duft"
              className="rounded-xl border border-white/15 bg-white px-3 py-2 text-[12px] font-semibold text-[#17120d] transition hover:bg-[#fff7e7]"
            >
              Düfte entdecken
            </a>
          </div>
        </div>

        <div className="relative mt-5 rounded-xl border border-white/10 bg-white/[0.045] px-3.5 py-3 text-[11.5px] leading-5 text-white/55">
          Diese Funktion benötigt kein Konto. Produkt-IDs deiner
          Merkliste und Sammlung werden ausschließlich im lokalen
          Browser-Speicher dieses Geräts abgelegt. Löschst du
          Browserdaten oder wechselst das Gerät, ist die Liste nicht
          automatisch verfügbar.
        </div>
        <div className="relative mt-3 flex flex-wrap items-center gap-2">
          {library.wishlist.length + library.owned.length > 0 ? (
            <button
              type="button"
              onClick={exportBackup}
              className="rounded-xl border border-white/15 px-3 py-2 text-[11.5px] font-semibold text-white/85 transition hover:border-[#d9bd82]/45"
            >
              Duftliste sichern
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => importInputRef.current?.click()}
            className="rounded-xl border border-white/15 px-3 py-2 text-[11.5px] font-semibold text-white/85 transition hover:border-[#d9bd82]/45"
          >
            Sicherung importieren
          </button>
          <input
            ref={importInputRef}
            type="file"
            accept=".json,application/json"
            onChange={(event) => void importBackup(event)}
            className="sr-only"
            aria-label="DUFYND-Duftliste aus JSON-Datei importieren"
          />
          <p className="w-full text-[10.5px] leading-4 text-white/55">
            Die JSON-Datei enthält nur Produkt-IDs. Beim Import ersetzt sie die Auswahl auf diesem Gerät.
          </p>
          <p role="status" className="w-full text-[11px] text-[#e8cf9d]">
            {backupStatus}
          </p>
        </div>
      </section>

      {mode === "owned" && owned.length >= 2 ? (
        <section className="dufynd-library-profile mt-5 rounded-2xl border border-(--line) bg-(--card) p-5 shadow-(--shadow-sm)">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-[18px] font-semibold">
                Dein Sammlungsprofil
              </h2>
              <p className="mt-1 max-w-2xl text-[12px] leading-5 text-(--ink-soft)">
                Eine grobe Übersicht aus den vier redaktionellen
                DUFYND-Profilachsen. Sie beschreibt deine gespeicherten
                Düfte, nicht deinen persönlichen Geschmack.
              </p>
              <p className="mt-1 text-[11px] leading-5 text-(--ink-soft)">
                Erst wenn du oben ausdrücklich „Mit meiner Sammlung beraten
                lassen“ auswählst, wird eine kompakte Zusammenfassung für
                genau diese Beratung an den Advisor übergeben.
              </p>
            </div>
            <span className="rounded-full border border-(--line) px-3 py-1.5 text-[11px] font-semibold text-(--ink-soft)">
              {owned.length} Düfte
            </span>
          </div>

          <div
            className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
            aria-label="Visuelles Sammlungsprofil"
          >
            {profile.axisStats.map((axis) => {
              const width =
                axis.average == null
                  ? 0
                  : Math.max(0, Math.min(100, axis.average * 10));

              return (
                <div
                  key={axis.key}
                  className="dufynd-library-profile-axis rounded-xl border border-(--line) bg-(--well)/35 p-3"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="text-[11px] font-medium text-(--ink-soft)">
                      {axis.label}
                    </div>
                    <div className="text-[18px] font-semibold tabular-nums">
                      {formatOneDecimal(axis.average)}
                      <span className="ml-1 text-[10px] font-normal text-(--ink-soft)">
                        /10
                      </span>
                    </div>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-(--line)">
                    <div
                      className="h-full rounded-full bg-(--accent-strong)"
                      style={{ width: `${width}%` }}
                    />
                  </div>
                  <div className="mt-2 text-[10.5px] leading-4 text-(--ink-soft)">
                    {axis.strongCount}{" "}
                    {axis.strongCount === 1
                      ? "deutlicher Vertreter"
                      : "deutliche Vertreter"}
                    {" "}ab 7/10
                  </div>
                </div>
              );
            })}
          </div>

          {profile.topAccords.length ? (
            <div className="mt-5">
              <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-(--ink-soft)">
                Häufige Akkorde in deiner Sammlung
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {profile.topAccords.map((item) => (
                  <span
                    key={item.accord}
                    className="rounded-full border border-(--line) bg-(--surface) px-3 py-1.5 text-[11.5px] text-(--ink)"
                  >
                    {accordLabel(item.accord)} ·{" "}
                    {item.count}
                  </span>
                ))}
              </div>
            </div>
          ) : null}

          {profile.suggestions.length ? (
            <div className="mt-5 border-t border-(--line) pt-5">
              <h3 className="text-[15px] font-semibold">
                Mögliche Profil-Ergänzungen
              </h3>
              <p className="mt-1 max-w-2xl text-[11.5px] leading-5 text-(--ink-soft)">
                Nur falls du bewusst mehr Vielfalt möchtest: In den
                folgenden Profilachsen hat deine Sammlung aktuell keinen
                deutlichen Vertreter ab 7/10. Das ist keine Kaufempfehlung
                und kein Qualitätsurteil.
              </p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {profile.suggestions.map((item) => (
                  <a
                    key={item.fragrance.product_id}
                    href={`/duft/${item.fragrance.slug}`}
                    className="dufynd-library-suggestion rounded-xl border border-(--line) bg-(--well)/35 p-3 transition hover:border-(--accent)"
                  >
                    <div className="text-[10.5px] font-semibold uppercase tracking-[0.06em] text-(--ink-soft)">
                      {item.reason}
                    </div>
                    <div className="mt-1 text-[13px] font-semibold text-(--ink)">
                      {item.fragrance.brand}{" "}
                      {item.fragrance.name}
                    </div>
                  </a>
                ))}
              </div>
            </div>
          ) : (
            <p className="mt-5 border-t border-(--line) pt-4 text-[11.5px] leading-5 text-(--ink-soft)">
              In allen vier groben Profilachsen ist mindestens ein Duft
              mit einem DUFYND-Wert ab 7/10 vorhanden. Das bedeutet
              nicht automatisch, dass die Sammlung vollständig oder
              ausgewogen ist.
            </p>
          )}
        </section>
      ) : null}

      {mode === "owned" && owned.length === 1 ? (
        <section className="mt-5 rounded-2xl border border-(--line) bg-(--card) p-4 text-[12px] leading-5 text-(--ink-soft)">
          Füge mindestens einen weiteren Duft hinzu, damit DUFYND erste
          grobe Profil-Schwerpunkte deiner Sammlung gegenüberstellen kann.
        </section>
      ) : null}

      {active.length ? (
        <>
          <section
            className="dufynd-library-grid mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
            data-dufynd-library-grid
          >
            {active.map((fragrance) => (
              <FragranceCard
                key={fragrance.product_id}
                fragrance={fragrance}
                source={
                  mode === "wishlist"
                    ? "wishlist_page"
                    : "collection_page"
                }
              />
            ))}
          </section>

          <div className="mt-5 flex justify-end">
            <button
              type="button"
              onClick={() => {
                if (
                  !window.confirm(
                    "Merkliste und Sammlung auf diesem Gerät wirklich vollständig löschen?",
                  )
                ) {
                  return;
                }
                if (!clearFragranceLibrary()) {
                  setBackupStatus("Löschen fehlgeschlagen. Deine gespeicherten Duftdaten bleiben erhalten. Bitte versuche es erneut.");
                  return;
                }
                setLibrary(emptyState());
                setBackupStatus("Persönliche Duftdaten auf diesem Gerät gelöscht.");
              }}
              className="text-[11px] font-medium text-(--ink-soft) underline-offset-2 hover:underline"
            >
              Persönliche Duftdaten auf diesem Gerät löschen
            </button>
          </div>
        </>
      ) : (
        <section className="dufynd-library-empty mt-5 rounded-2xl border border-dashed border-(--line) bg-(--card) px-5 py-10 text-center">
          <h2 className="text-[17px] font-semibold">
            {emptyTitle}
          </h2>
          <p className="mx-auto mt-2 max-w-lg text-[12.5px] leading-5 text-(--ink-soft)">
            {emptyText}
          </p>
          <a
            href="/duft"
            className="mt-4 inline-flex rounded-xl bg-(--ink) px-4 py-2.5 text-[12px] font-semibold text-(--surface)"
          >
            Duftkatalog öffnen
          </a>
        </section>
      )}
    </>
  );
}
