import AcquisitionInternalLink from "@/components/AcquisitionInternalLink";
import NoteIcon from "@/components/NoteIcon";
import { noteLabel } from "@/lib/noteLabels";

type FragranceNotes = {
  top: string[];
  heart: string[];
  base: string[];
  key: string[];
  supporting: string[];
};

type NoteGroup = {
  id: string;
  number: string;
  label: string;
  description: string;
  notes: string[];
};

function uniqueNotes(notes: string[]): string[] {
  const used = new Set<string>();
  return notes.filter((note) => {
    const key = note.trim().toLocaleLowerCase("de-DE");
    if (!key || used.has(key)) return false;
    used.add(key);
    return true;
  });
}

function NoteCard({ group, interactive }: { group: NoteGroup; interactive: boolean }) {
  return (
    <section className="dufynd-notes-group" data-dufynd-notes-group={group.id}>
      <div className="dufynd-notes-group-heading">
        <span className="dufynd-notes-index" aria-hidden>{group.number}</span>
        <div>
          <h3>{group.label}</h3>
          <p>{group.description}</p>
        </div>
      </div>
      {group.notes.length ? (
        <ul className="dufynd-notes-chips">
          {uniqueNotes(group.notes).map((note) => (
            <li key={note}>
              {interactive ? <AcquisitionInternalLink
                href={`/duft?q=${encodeURIComponent(noteLabel(note))}`}
                aria-label={`Weitere Düfte mit ${noteLabel(note)} entdecken`}
                className="dufynd-notes-chip"
              >
                <NoteIcon note={note} className="h-4 w-4 shrink-0" />
                <span>{noteLabel(note)}</span>
                <span aria-hidden>↗</span>
              </AcquisitionInternalLink> : <span className="dufynd-notes-chip"><NoteIcon note={note} className="h-4 w-4 shrink-0" /><span>{noteLabel(note)}</span></span>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="dufynd-notes-unavailable">Nicht einzeln dokumentiert</p>
      )}
    </section>
  );
}

/** Source-honest visual grammar. Never infer a time pyramid from key notes. */
export default function FragranceNotesOverview({ notes, interactive = true }: { notes: FragranceNotes; interactive?: boolean }) {
  const hasPyramid = Boolean(
    notes.top.length || notes.heart.length || notes.base.length,
  );
  const primary: NoteGroup[] = hasPyramid
    ? [
        { id: "top", number: "01", label: "Kopfnoten", description: "Dokumentierter Auftakt", notes: notes.top },
        { id: "heart", number: "02", label: "Herznoten", description: "Dokumentiertes Herz", notes: notes.heart },
        { id: "base", number: "03", label: "Basisnoten", description: "Dokumentierte Basis", notes: notes.base },
      ]
    : [
        { id: "key", number: "01", label: "Schlüsselnoten", description: "Dokumentierte prägende Noten", notes: notes.key },
        { id: "supporting", number: "02", label: "Weitere Noten", description: "Ergänzend dokumentierte Noten", notes: notes.supporting },
      ];

  const assigned = new Set(
    [...notes.top, ...notes.heart, ...notes.base].map((note) =>
      note.trim().toLocaleLowerCase("de-DE"),
    ),
  );
  const complementary = uniqueNotes([...notes.key, ...notes.supporting]).filter(
    (note) => !assigned.has(note.trim().toLocaleLowerCase("de-DE")),
  );
  const documented = uniqueNotes([
    ...notes.top, ...notes.heart, ...notes.base, ...notes.key, ...notes.supporting,
  ]);

  return (
    <section
      id="duftnoten"
      className="dufynd-notes-overview scroll-mt-24"
      data-dufynd-note-layout={hasPyramid ? "pyramid" : "key-notes"}
      aria-labelledby="dufynd-notes-title"
    >
      <header className="dufynd-notes-overview-header">
        <div>
          <p className="dufynd-notes-overview-eyebrow">DUFYND / DIE KOMPOSITION</p>
          <h2 id="dufynd-notes-title">Duftnoten auf einen Blick</h2>
        </div>
        <p>
          {hasPyramid
            ? "Kopf, Herz und Basis – ausschließlich nach den dokumentierten Angaben."
            : "Dokumentierte Duftnoten – ohne erfundene Reihenfolge oder Duftpyramide."}
        </p>
      </header>
      {documented.length ? (
        <>
          <div className="dufynd-notes-groups" data-dufynd-note-count={documented.length}>
            {primary.map((group) => <NoteCard key={group.id} group={group} interactive={interactive} />)}
          </div>
          {hasPyramid && complementary.length ? (
            <div className="dufynd-notes-supplementary">
              <h3>Weitere dokumentierte Noten</h3>
              <ul className="dufynd-notes-chips">
                {complementary.map((note) => (
                  <li key={note}>
                    {interactive ? <AcquisitionInternalLink
                      href={`/duft?q=${encodeURIComponent(noteLabel(note))}`}
                      className="dufynd-notes-chip"
                    >
                      <NoteIcon note={note} className="h-4 w-4 shrink-0" />
                      <span>{noteLabel(note)}</span>
                      <span aria-hidden>↗</span>
                    </AcquisitionInternalLink> : <span className="dufynd-notes-chip"><NoteIcon note={note} className="h-4 w-4 shrink-0" /><span>{noteLabel(note)}</span></span>}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      ) : (
        <p className="dufynd-notes-empty">
          Für diese exakte Duftvariante sind noch keine nachgewiesenen Duftnoten hinterlegt.
        </p>
      )}
      <p className="dufynd-notes-method">
        Die Kategorien beschreiben dokumentierte Duftangaben, keine gemessene Wirkungsdauer oder Laboranalyse.
      </p>
    </section>
  );
}
