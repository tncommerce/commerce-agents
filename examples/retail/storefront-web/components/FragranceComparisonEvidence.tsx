import { accordLabel } from "@/lib/accordLabels";
import { noteLabel } from "@/lib/noteLabels";
import type { StaticFragrance } from "@/lib/fragranceCatalog";

type ComparisonEvidenceFragrance = Pick<
  StaticFragrance,
  "name" | "accords" | "notes"
>;

function normalizedTerm(value: string): string {
  return value.trim().normalize("NFKC").toLocaleLowerCase("de-DE");
}

function uniqueTerms(values: readonly string[]): string[] {
  const seen = new Set<string>();
  return values.filter((value) => {
    const key = normalizedTerm(value);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function allDocumentedNotes(fragrance: ComparisonEvidenceFragrance): string[] {
  return uniqueTerms([
    ...fragrance.notes.top,
    ...fragrance.notes.heart,
    ...fragrance.notes.base,
    ...fragrance.notes.key,
    ...fragrance.notes.supporting,
  ]);
}

function overlappingTerms(left: string[], right: string[]): string[] {
  const rightKeys = new Set(right.map(normalizedTerm));
  return uniqueTerms(left).filter((term) =>
    rightKeys.has(normalizedTerm(term)),
  );
}

function exclusiveTerms(left: string[], right: string[]): string[] {
  const rightKeys = new Set(right.map(normalizedTerm));
  return uniqueTerms(left).filter(
    (term) => !rightKeys.has(normalizedTerm(term)),
  );
}

function EvidenceChips({
  terms,
  label,
  formatter,
}: {
  terms: string[];
  label: string;
  formatter: (term: string) => string;
}) {
  return (
    <ul aria-label={label} className="mt-2 flex flex-wrap gap-2">
      {terms.map((term) => (
        <li
          key={normalizedTerm(term)}
          className="rounded-full border border-(--line) bg-(--surface) px-2.5 py-1.5 text-[11px] font-medium text-(--ink)"
        >
          {formatter(term)}
        </li>
      ))}
    </ul>
  );
}

/**
 * Shows only exact overlaps in recorded scent data.
 * Never infer a clone, a percentage match or a purchase recommendation
 * from a broad profile/accord intersection.
 */
export default function FragranceComparisonEvidence({
  left,
  right,
}: {
  left: ComparisonEvidenceFragrance;
  right: ComparisonEvidenceFragrance;
}) {
  const leftAccords = uniqueTerms(left.accords);
  const rightAccords = uniqueTerms(right.accords);
  const sharedAccords = overlappingTerms(leftAccords, rightAccords).slice(0, 5);
  const leftOnly = exclusiveTerms(leftAccords, rightAccords).slice(0, 4);
  const rightOnly = exclusiveTerms(rightAccords, leftAccords).slice(0, 4);
  const sharedNotes = overlappingTerms(
    allDocumentedNotes(left),
    allDocumentedNotes(right),
  ).slice(0, 5);
  const hasDocumentedOverlap =
    sharedAccords.length > 0 || sharedNotes.length > 0;

  return (
    <section
      aria-labelledby="comparison-evidence-heading"
      className="mt-4 overflow-hidden rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) sm:p-5"
      data-dufynd-comparison-evidence
    >
      <div className="max-w-2xl">
        <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-(--accent-ink)">
          DUFYND · Duft-DNA verstehen
        </div>
        <h3
          id="comparison-evidence-heading"
          className="mt-1 text-[18px] font-semibold tracking-[-0.02em] text-(--ink)"
        >
          Was verbindet diese beiden Düfte?
        </h3>
        <p className="mt-2 text-[12px] leading-5 text-(--ink-soft)">
          Hier zeigen wir ausschließlich Überschneidungen und Unterschiede,
          die in den hinterlegten Duftprofilen dokumentiert sind.
        </p>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-(--line) bg-(--well)/35 p-3.5">
          <h4 className="text-[12px] font-semibold text-(--ink)">
            Gemeinsame Duftakkorde
          </h4>
          {sharedAccords.length ? (
            <EvidenceChips
              terms={sharedAccords}
              label="Dokumentierte gemeinsame Duftakkorde"
              formatter={accordLabel}
            />
          ) : (
            <p className="mt-2 text-[11px] leading-5 text-(--ink-soft)">
              Keine gemeinsame Akkordangabe dokumentiert.
            </p>
          )}
        </div>
        <div className="rounded-xl border border-(--line) bg-(--well)/35 p-3.5">
          <h4 className="text-[12px] font-semibold text-(--ink)">
            Gemeinsame Duftnoten
          </h4>
          {sharedNotes.length ? (
            <EvidenceChips
              terms={sharedNotes}
              label="Dokumentierte gemeinsame Duftnoten"
              formatter={noteLabel}
            />
          ) : (
            <p className="mt-2 text-[11px] leading-5 text-(--ink-soft)">
              Keine übereinstimmende Note in den vorhandenen Notenlisten.
            </p>
          )}
        </div>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {(
          [
            { key: "left", fragrance: left, terms: leftOnly },
            { key: "right", fragrance: right, terms: rightOnly },
          ] as const
        ).map(({ key, fragrance, terms }) => (
          <div
            key={key}
            className="rounded-xl border border-(--line) p-3.5"
          >
            <h4 className="text-[12px] font-semibold text-(--ink)">
              {fragrance.name}: eigene Akzente
            </h4>
            {terms.length ? (
              <EvidenceChips
                terms={terms}
                label={`Nur für ${fragrance.name} hinterlegte Akkorde`}
                formatter={accordLabel}
              />
            ) : (
              <p className="mt-2 text-[11px] leading-5 text-(--ink-soft)">
                Keine zusätzlichen Akkorde in diesem Datenausschnitt.
              </p>
            )}
          </div>
        ))}
      </div>

      <p className="mt-3 text-[11px] leading-5 text-(--ink-soft)">
        {hasDocumentedOverlap
          ? "Gemeinsame Angaben sind Orientierungspunkte, kein Beweis für identischen Duft oder eine bestätigte Dupe-Beziehung."
          : "Keine belegte Überschneidung in diesen Datenausschnitten: Das schließt einen ähnlichen Dufteindruck nicht aus."}
        {" "}Die Notenlisten können unterschiedlich vollständig sein.
        Händlerangebote und aktuelle Preise werden separat geprüft.
      </p>
    </section>
  );
}
