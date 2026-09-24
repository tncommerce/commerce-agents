import type { ReactNode } from "react";

type Motif = "citrus" | "flower" | "leaf" | "wood" | "spice" | "sweet" | "resin" | "fruit" | "fresh" | "abstract";

const MOTIFS: { motif: Motif; names: string[] }[] = [
  { motif: "flower", names: ["orange blossom", "neroli", "jasmine", "lavender", "violet", "rose", "iris", "orris", "geranium", "magnolia", "carnation", "floral", "lily", "orchid"] },
  { motif: "citrus", names: ["bergamot", "grapefruit", "lemon", "mandarin", "orange", "lime", "citron", "petit grain"] },
  { motif: "leaf", names: ["patchouli", "vetiver", "sage", "rosemary", "basil", "mint", "moss", "tea", "maté", "wormwood", "papyrus"] },
  { motif: "wood", names: ["wood", "cedar", "sandal", "birch", "oud", "cashmere", "cashmeran"] },
  { motif: "spice", names: ["pepper", "ginger", "cardamom", "cinnamon", "nutmeg", "coriander", "spices"] },
  { motif: "sweet", names: ["vanilla", "tonka", "honey", "praline", "cocoa", "chestnut", "coumarin"] },
  { motif: "resin", names: ["amber", "incense", "frankincense", "labdanum", "elemi", "musk", "ambrox", "leather", "tobacco", "opium"] },
  { motif: "fruit", names: ["apple", "pineapple", "cherry", "melon", "blackcurrant"] },
  { motif: "fresh", names: ["aldehyde", "aquatic", "ozonic"] },
];

function motifFor(note: string): Motif {
  const normalized = note.toLocaleLowerCase("en-US");
  return MOTIFS.find(({ names }) => names.some((name) => normalized.includes(name)))?.motif ?? "abstract";
}

const paths: Record<Motif, ReactNode> = {
  citrus: <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="5.5" /><path d="M12 6.5v11M6.5 12h11M8.1 8.1l7.8 7.8M15.9 8.1l-7.8 7.8" /></>,
  flower: <><circle cx="12" cy="12" r="2" /><path d="M12 10c-3-5-1-7 1-6 2 1 1 4-1 6Zm2 2c5-3 7-1 6 1-1 2-4 1-6-1Zm-2 2c3 5 1 7-1 6-2-1-1-4 1-6Zm-2-2c-5 3-7 1-6-1 1-2 4-1 6 1Z" /></>,
  leaf: <><path d="M19 5C11 5 5 8 5 15a4 4 0 0 0 4 4c7 0 10-6 10-14ZM5 20c2-5 6-8 11-11" /></>,
  wood: <><path d="M8 20V8l4-5 4 5v12M5 20h14M8 10h8M12 3v17M9 15l3 2 3-2" /></>,
  spice: <><path d="M12 3c1.4 4.2 2.8 5.6 7 7-4.2 1.4-5.6 2.8-7 7-1.4-4.2-2.8-5.6-7-7 4.2-1.4 5.6-2.8 7-7ZM18.5 16.5l.6 1.4 1.4.6-1.4.6-.6 1.4-.6-1.4-1.4-.6 1.4-.6.6-1.4Z" /></>,
  sweet: <><path d="M12 3c-2 3-6 7-6 11a6 6 0 0 0 12 0c0-4-4-8-6-11ZM9 15c0 2 1 3 3 3" /></>,
  resin: <><path d="M12 2 4 9v9l8 4 8-4V9l-8-7ZM4 9l8 4 8-4M12 13v9M8 6l8 4" /></>,
  fruit: <><path d="M12 8c-5-4-9 0-8 5 1 6 5 9 8 7 3 2 7-1 8-7 1-5-3-9-8-5ZM12 8c0-3 1-5 4-6M12 7c-2-3-4-3-6-2" /></>,
  fresh: <><path d="M3 12h18M12 3v18M5.6 5.6l12.8 12.8M18.4 5.6 5.6 18.4M9 3l3 3 3-3M9 21l3-3 3 3" /></>,
  abstract: <><circle cx="12" cy="12" r="8" /><path d="M12 6v12M6 12h12M8 8l8 8M16 8l-8 8" /></>,
};

export default function NoteIcon({ note, className = "h-4 w-4" }: { note: string; className?: string }) {
  return (
    <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" className={className}>
      {paths[motifFor(note)]}
    </svg>
  );
}
