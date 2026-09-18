import LegalFooter from "@/components/LegalFooter";

export default function NotFound() {
  return (
    <main className="min-h-screen bg-(--ground) px-4 py-12 text-(--ink) sm:px-6">
      <div className="mx-auto max-w-xl">
        <section className="rounded-3xl border border-(--line) bg-(--card) p-6 shadow-(--shadow-sm) sm:p-8">
          <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-(--ink-soft)">
            404
          </div>
          <h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em]">
            Diese Seite gibt es hier nicht.
          </h1>
          <p className="mt-3 text-[14px] leading-6 text-(--ink-soft)">
            Der Link ist möglicherweise veraltet oder der Duft wurde unter einer anderen Adresse veröffentlicht.
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            <a
              href="/duft"
              className="rounded-xl bg-(--accent) px-4 py-2.5 text-[13px] font-semibold text-white"
            >
              Duftkatalog öffnen
            </a>
            <a
              href="/"
              className="rounded-xl border border-(--line) bg-(--card) px-4 py-2.5 text-[13px] font-semibold text-(--ink)"
            >
              Zur Duftberatung
            </a>
          </div>
        </section>
        <LegalFooter />
      </div>
    </main>
  );
}
