"use client";

export default function ManualShareLink({ url }: { url: string }) {
  if (!url) return null;

  return (
    <label className="block w-full min-w-0 text-[11px] text-(--ink-soft)">
      Link zum manuellen Kopieren
      <input
        type="text"
        readOnly
        value={url}
        onFocus={(event) => event.currentTarget.select()}
        className="mt-1 block w-full min-w-0 rounded-lg border border-(--line) bg-(--surface) px-2.5 py-2 text-[12px] text-(--ink)"
      />
    </label>
  );
}
