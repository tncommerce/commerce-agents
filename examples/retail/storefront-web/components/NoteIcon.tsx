import type { ReactNode } from "react";

type Motif =
  | "bergamot"
  | "grapefruit"
  | "jasmine"
  | "patchouli"
  | "citrus"
  | "flower"
  | "leaf"
  | "root"
  | "wood"
  | "spice"
  | "pepper"
  | "vanilla"
  | "honey"
  | "sweet"
  | "resin"
  | "amber"
  | "musk"
  | "leather"
  | "tobacco"
  | "fruit"
  | "apple"
  | "pineapple"
  | "cherry"
  | "tea"
  | "cocoa"
  | "fresh"
  | "incense"
  | "moss"
  | "abstract";

const MOTIFS: { motif: Motif; names: string[] }[] = [
  { motif: "bergamot", names: ["calabrian bergamot", "bergamot"] },
  { motif: "grapefruit", names: ["grapefruit"] },
  { motif: "jasmine", names: ["jasmine sambac", "jasmine"] },
  { motif: "patchouli", names: ["patchouli"] },
  { motif: "honey", names: ["honey"] },
  { motif: "vanilla", names: ["bourbon vanilla", "vanilla orchid", "vanilla"] },
  { motif: "tobacco", names: ["tobacco"] },
  { motif: "leather", names: ["leather"] },
  { motif: "incense", names: ["frankincense", "incense"] },
  { motif: "pepper", names: ["timut pepper", "pink pepper", "pepper"] },
  { motif: "pineapple", names: ["pineapple"] },
  { motif: "cherry", names: ["black cherry", "cherry"] },
  { motif: "apple", names: ["green apple", "apple"] },
  { motif: "tea", names: ["black tea", "tea", "maté"] },
  { motif: "cocoa", names: ["cocoa"] },
  { motif: "moss", names: ["oak moss", "moss"] },
  { motif: "root", names: ["vetiver", "orris root"] },
  { motif: "musk", names: ["white musk", "pink musk", "musk", "ambrette seed", "ambrette"] },
  { motif: "amber", names: ["ambergris", "amberwood", "crystal amber", "ambrofix", "ambroxan", "ambrox", "amber"] },
  { motif: "flower", names: ["orange blossom", "neroli", "lavender", "violet", "rose", "iris", "orris", "geranium", "magnolia", "carnation", "floral", "lily", "orchid", "mahonia"] },
  { motif: "citrus", names: ["lemon", "mandarin", "orange", "lime", "citron", "citrus", "petit grain"] },
  { motif: "leaf", names: ["sage", "rosemary", "basil", "mint", "papyrus", "wormwood"] },
  { motif: "wood", names: ["akigalawood", "georgywood", "guaiac wood", "wood", "cedar", "cypress", "sandal", "birch", "oud", "cashmere", "cashmeran"] },
  { motif: "spice", names: ["ginger", "cardamom", "cinnamon", "nutmeg", "coriander", "spices"] },
  { motif: "sweet", names: ["tonka", "praline", "chestnut", "coumarin"] },
  { motif: "resin", names: ["labdanum", "elemi", "opium"] },
  { motif: "fruit", names: ["blackcurrant", "raspberry", "melon"] },
  { motif: "fresh", names: ["aldehyde", "aquatic", "ozonic"] },
];

function motifFor(note: string): Motif {
  const normalized = note.toLocaleLowerCase("en-US");
  return MOTIFS.find(({ names }) =>
    names.some((name) => normalized.includes(name)),
  )?.motif ?? "abstract";
}

const paths: Record<Motif, ReactNode> = {
  bergamot: (
    <>
      <circle cx="12" cy="12" r="8.2" fill="#DCE66A" stroke="#66743A" strokeWidth="1.05" />
      <circle cx="12" cy="12" r="5.8" fill="#F5D86B" stroke="#8A8D45" strokeWidth=".75" />
      <path d="M12 6.2v11.6M6.2 12h11.6M7.9 7.9l8.2 8.2M16.1 7.9l-8.2 8.2" stroke="#FFF0A8" strokeWidth=".85" />
      <path d="M14.5 3.9c1.5-1.1 3.1-1.2 4.5-.6-1 1.6-2.5 2.5-4.4 2.5" fill="#6E9148" stroke="#4F7135" strokeWidth=".75" />
    </>
  ),
  grapefruit: (
    <>
      <circle cx="12" cy="12" r="8.3" fill="#F4C85B" stroke="#A86E3F" strokeWidth="1.05" />
      <circle cx="12" cy="12" r="6.05" fill="#F47F88" stroke="#E06170" strokeWidth=".7" />
      <circle cx="12" cy="12" r="1.05" fill="#F7D8B7" stroke="none" />
      <path d="M12 6v5M18 12h-5M12 18v-5M6 12h5M7.8 7.8l3.5 3.5M16.2 7.8l-3.5 3.5M16.2 16.2l-3.5-3.5M7.8 16.2l3.5-3.5" stroke="#FFD7CF" strokeWidth=".78" />
    </>
  ),
  jasmine: (
    <>
      <path d="M12 10.3C9.8 5.8 6.8 4.4 5.6 6.3c-1.1 1.9 1.3 4.1 5.2 5.1" fill="#FFFDF7" stroke="#C8C6BF" strokeWidth=".8" />
      <path d="M13.7 11.1c4.5-2.2 5.9-5.2 4-6.4-1.9-1.1-4.1 1.3-5.1 5.2" fill="#FFFDF7" stroke="#C8C6BF" strokeWidth=".8" />
      <path d="M13.7 12.9c4.5 2.2 5.9 5.2 4 6.4-1.9 1.1-4.1-1.3-5.1-5.2" fill="#FFFDF7" stroke="#C8C6BF" strokeWidth=".8" />
      <path d="M10.3 12.9c-4.5 2.2-5.9 5.2-4 6.4 1.9 1.1 4.1-1.3 5.1-5.2" fill="#FFFDF7" stroke="#C8C6BF" strokeWidth=".8" />
      <circle cx="12" cy="12" r="2.15" fill="#E9B83F" stroke="#B68C28" strokeWidth=".75" />
      <circle cx="12" cy="12" r=".75" fill="#8A6730" stroke="none" />
    </>
  ),
  patchouli: (
    <>
      <path d="M11.2 20C5.8 17.4 4 12.8 6 8.5c1.7-3.7 5-5.2 6.4-5.6 1.6 4.7 1.4 10.7-1.2 17.1Z" fill="#5B874A" stroke="#355E34" strokeWidth=".9" />
      <path d="M13 19.3c5.1-2.4 7.1-6.7 5.3-10.8-1.4-3.3-4.3-4.8-5.8-5.4-1.2 4.7-.9 10.4.5 16.2Z" fill="#79A05A" stroke="#476D3C" strokeWidth=".9" />
      <path d="M7.2 9.7c2 2.6 3.2 5.4 3.9 9M17 9.6c-1.9 2.8-3 5.7-3.7 9" stroke="#D8E0A4" strokeWidth=".72" />
      <path d="M12.1 18.4v3" stroke="#5A4732" strokeWidth="1" />
    </>
  ),
  citrus: (
    <>
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" r="5.5" />
      <path d="M12 6.5v11M6.5 12h11M8.1 8.1l7.8 7.8M15.9 8.1l-7.8 7.8" />
    </>
  ),
  flower: (
    <>
      <circle cx="12" cy="12" r="1.8" />
      <path d="M12 10c-3-5-1-7 1-6 2 1 1 4-1 6Zm2 2c5-3 7-1 6 1-1 2-4 1-6-1Zm-2 2c3 5 1 7-1 6-2-1-1-4 1-6Zm-2-2c-5 3-7 1-6-1 1-2 4-1 6 1Z" />
    </>
  ),
  leaf: (
    <>
      <path d="M19 5C11 5 5 8 5 15a4 4 0 0 0 4 4c7 0 10-6 10-14Z" />
      <path d="M5 20c2-5 6-8 11-11" />
    </>
  ),
  root: (
    <>
      <path d="M12 3v8M8 6c1.3 1.2 2.7 1.7 4 1.7S14.7 7.2 16 6" />
      <path d="M12 11c-1 3-3 4-5 6M12 11c1 3 3 4 5 6M10 14l-1 6M14 14l1 6" />
    </>
  ),
  wood: (
    <>
      <path d="M8 20V8l4-5 4 5v12M5 20h14M8 10h8M12 3v17" />
      <path d="M9 15l3 2 3-2" />
    </>
  ),
  spice: (
    <>
      <g transform="rotate(-28 9 13)">
        <rect x="6.2" y="5.3" width="3.1" height="14.2" rx="1.45" fill="#A96332" stroke="#6F3D24" strokeWidth=".85" />
        <rect x="9.1" y="5.8" width="3" height="13.6" rx="1.4" fill="#C77B3D" stroke="#7B4828" strokeWidth=".85" />
        <path d="M7.1 7.2h1.5M10 8h1.4M7 16.7h1.5M9.9 15.8h1.4" stroke="#E3A76C" strokeWidth=".65" />
      </g>
      <path d="M16.7 5.4 18 9l3.6.3-2.8 2.3.9 3.5-3-2-3 2 .9-3.5-2.8-2.3 3.6-.3 1.3-3.6Z" fill="#7B4C2F" stroke="#56301E" strokeWidth=".72" />
      <circle cx="17" cy="10" r="1.05" fill="#D5A05F" stroke="none" />
    </>
  ),
  pepper: (
    <>
      <circle cx="9" cy="9" r="2.5" />
      <circle cx="15.5" cy="12" r="2.3" />
      <circle cx="9.5" cy="16" r="2" />
      <path d="M11 7c2-2 4-2 6-1" />
    </>
  ),
  vanilla: (
    <>
      <path d="M7.1 20.1c1-6.8 3.2-12.6 7.8-17.1" stroke="#4D3528" strokeWidth="2.15" />
      <path d="M10.6 20.3c.5-6.1 2-11 5.2-15.2" stroke="#7C5135" strokeWidth="1.75" />
      <path d="M14.2 8.3c2.7-3.8 5.3-3.9 6.2-2.2.9 1.8-.7 3.9-4.5 4.4 2.9 1.7 3.4 4.2 1.7 5.2-1.8 1-3.7-.5-4.2-3.6-1.7 2.7-4.2 3.2-5.1 1.5-.9-1.7.6-3.6 3.6-4-2.7-1.7-3.2-4-1.5-5 1.6-.9 3.4.5 3.8 3.7Z" fill="#FFF7E5" stroke="#D8C6A1" strokeWidth=".72" />
      <circle cx="14.1" cy="9.7" r="1.45" fill="#E6B94C" stroke="#B9862F" strokeWidth=".65" />
    </>
  ),
  honey: (
    <>
      <path d="M8 5h8l4 7-4 7H8l-4-7 4-7Z" />
      <path d="M12 8c-1.4 2-3 3.8-3 5.6a3 3 0 0 0 6 0C15 11.8 13.4 10 12 8Z" />
    </>
  ),
  sweet: (
    <>
      <path d="M12 3c-2 3-6 7-6 11a6 6 0 0 0 12 0c0-4-4-8-6-11Z" />
      <path d="M9 15c0 2 1 3 3 3" />
    </>
  ),
  resin: (
    <>
      <path d="M12 2 4 9v9l8 4 8-4V9l-8-7Z" />
      <path d="M4 9l8 4 8-4M12 13v9M8 6l8 4" />
    </>
  ),
  amber: (
    <>
      <path d="M12 3 18 8l-2 9-4 4-4-4-2-9 6-5Z" />
      <path d="m8 9 4 2 4-2M10 15h4" />
    </>
  ),
  musk: (
    <>
      <path d="M12 4c3 2 5 5 5 8a5 5 0 0 1-10 0c0-3 2-6 5-8Z" />
      <path d="M9 18c1.5-1 2-2.2 3-4 1 1.8 1.5 3 3 4" />
    </>
  ),
  leather: (
    <>
      <path d="M6 5c2 1 4 1 6 0 2 1 4 1 6 0l1 14c-5-2-9-2-14 0L6 5Z" />
      <path d="M9 9c2 1 4 1 6 0" />
    </>
  ),
  tobacco: (
    <>
      <path d="M12 3c4 3 6 7 5 11-1 4-4 6-8 6 1-3 1-6-2-9 2-4 3-6 5-8Z" />
      <path d="M10 18c1-5 2-8 5-11" />
    </>
  ),
  fruit: (
    <>
      <path d="M12 8c-5-4-9 0-8 5 1 6 5 9 8 7 3 2 7-1 8-7 1-5-3-9-8-5Z" />
      <path d="M12 8c0-3 1-5 4-6M12 7c-2-3-4-3-6-2" />
    </>
  ),
  apple: (
    <>
      <path d="M12 8c-4-3-8 0-7 5 1 5 4 8 7 6 3 2 6-1 7-6 1-5-3-8-7-5Z" />
      <path d="M12 7c0-2 1-4 3-5M12 6c-2-2-4-2-5-1" />
    </>
  ),
  pineapple: (
    <>
      <path d="M8 9h8l2 4-2 7H8l-2-7 2-4Z" />
      <path d="m9 9-2-4 4 2 1-4 1 4 4-2-2 4M8 12l8 5M16 12l-8 5" />
    </>
  ),
  cherry: (
    <>
      <circle cx="9" cy="15" r="3" />
      <circle cx="16" cy="15" r="3" />
      <path d="M9 12c1-5 3-7 7-8M16 12c0-4-1-6-4-8" />
    </>
  ),
  tea: (
    <>
      <path d="M5 8h12v7a5 5 0 0 1-5 5h-2a5 5 0 0 1-5-5V8Z" />
      <path d="M17 10h1.5a2.5 2.5 0 0 1 0 5H17M8 4c0 1 1 1.5 1 2.5M12 3c0 1 1 1.5 1 3" />
    </>
  ),
  cocoa: (
    <>
      <path d="M12 3c4 3 6 6 5 10s-3 7-5 8c-2-1-4-4-5-8S8 6 12 3Z" />
      <path d="M12 6v12M9 9l3 2 3-2M9 14l3 2 3-2" />
    </>
  ),
  fresh: (
    <>
      <path d="M3 12h18M12 3v18M5.6 5.6l12.8 12.8M18.4 5.6 5.6 18.4" />
      <path d="M9 3l3 3 3-3M9 21l3-3 3 3" />
    </>
  ),
  incense: (
    <>
      <path d="M6 19h12M8 16h8l1 3H7l1-3Z" />
      <path d="M12 15c-3-3 2-4 0-7-1-1-1-3 1-5M9 14c-2-2 1-3 0-5" />
    </>
  ),
  moss: (
    <>
      <path d="M4 18c2-5 4-7 7-6 1-4 5-5 7-2 2 3 1 6-1 8H4Z" />
      <path d="M7 18c1-2 2-3 4-3M13 18c1-2 2-3 4-3" />
    </>
  ),
  abstract: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 6v12M6 12h12M8 8l8 8M16 8l-8 8" />
    </>
  ),
};

export default function NoteIcon({
  note,
  className = "h-4 w-4",
}: {
  note: string;
  className?: string;
}) {
  const motif = motifFor(note);

  return (
    <svg
      data-dufynd-note-motif={motif}
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.35"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {paths[motif]}
    </svg>
  );
}
