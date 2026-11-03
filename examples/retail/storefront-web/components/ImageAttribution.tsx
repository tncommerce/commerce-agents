import type { FragranceVisualAsset } from "@/lib/fragranceCatalog";

export default function ImageAttribution({
  visual,
  compact = false,
}: {
  visual: FragranceVisualAsset | null | undefined;
  compact?: boolean;
}) {
  const attribution = String(visual?.attribution_text || "").trim();
  const licenseName = String(visual?.license_name || "").trim();
  const licenseUrl = String(visual?.license_url || "").trim();

  const merchantSource = visual?.provenance === "merchant_feed" &&
    visual.source_merchant_id === "top-parfuemerie" &&
    visual.source_page_url?.startsWith("https://www.topparfuemerie.de/");
  if (merchantSource) {
    if (compact) return null;
    return (
      <p data-original-photo-source="top-parfuemerie" className="text-[10px] leading-4 text-(--ink-soft)">Bild: <a href={visual.source_page_url!} target="_blank" rel="nofollow noopener noreferrer" className="font-medium text-(--accent-ink) hover:underline">top Parfümerie · Originalaufnahme</a></p>
    );
  }

  if (!attribution || !licenseName) return null;

  if (compact) {
    return (
      <span className="pointer-events-none absolute inset-x-2 bottom-1.5 rounded-md bg-white/90 px-1.5 py-1 text-center text-[8px] leading-3 text-(--ink-soft) shadow-sm">
        Bild: {attribution} · {licenseName}
      </span>
    );
  }

  return (
    <p className="text-[10px] leading-4 text-(--ink-soft)">
      Bild: {attribution} ·{" "}
      {licenseUrl ? (
        <a
          href={licenseUrl}
          target="_blank"
          rel="license noopener noreferrer"
          className="font-medium text-(--accent-ink) hover:underline"
        >
          {licenseName}
        </a>
      ) : (
        licenseName
      )}
      {visual?.share_alike_required ? " · ShareAlike" : ""}
    </p>
  );
}
