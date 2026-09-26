import type { ReactNode } from "react";

type Motif =
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
  { motif: "abstract", names: ["hedione"] },
  { motif: "honey", names: ["honey"] },
  { motif: "vanilla", names: ["bourbon vanilla", "vanilla orchid", "vanillin", "vanilla"] },
  { motif: "tobacco", names: ["tobacco"] },
  { motif: "leather", names: ["leather"] },
  { motif: "incense", names: ["frankincense", "incense"] },
  { motif: "pepper", names: ["timut pepper", "pink pepper", "pepper"] },
  { motif: "pineapple", names: ["pineapple"] },
  { motif: "cherry", names: ["black cherry", "cherry"] },
  { motif: "apple", names: ["green apple", "apple"] },
  { motif: "tea", names: ["black tea", "tea", "maté"] },
  { motif: "cocoa", names: ["coffee", "cocoa"] },
  { motif: "moss", names: ["oak moss", "moss"] },
  { motif: "root", names: ["vetiver", "orris root"] },
  { motif: "musk", names: ["white musk", "pink musk", "musk", "ambrette seed", "ambrette"] },
  { motif: "amber", names: ["ambergris", "amberwood", "crystal amber", "ambrofix", "ambroxan", "ambrox", "amber"] },
  { motif: "flower", names: ["orange blossom", "nectarine blossom", "everlasting essence", "frangipani", "freesia", "lavandin heart", "lotus", "neroli", "jasmine", "lavender", "violet", "rose", "iris", "orris", "geranium", "magnolia", "carnation", "floral", "lily", "orchid", "osmanthus", "peony", "white gardenia", "ylang-ylang", "mahonia"] },
  { motif: "citrus", names: ["bergamot", "grapefruit", "lemon", "mandarin", "orange", "lime", "citron", "citrus", "petitgrain", "petit grain"] },
  { motif: "leaf", names: ["patchouli", "sage", "rosemary", "basil", "mint", "papyrus", "wormwood", "davana", "fougère accord", "green accord", "green notes", "hay", "juniper"] },
  { motif: "wood", names: ["akigalawood", "georgywood", "guaiac wood", "wood", "cedar", "cypress", "sandal", "birch", "oud", "cashmere", "cashmeran", "cade oil", "mahogany", "pine"] },
  { motif: "spice", names: ["ginger", "cardamom", "cinnamon", "nutmeg", "coriander", "clove", "saffron", "spices"] },
  { motif: "sweet", names: ["tonka", "praline", "chestnut", "coumarin", "almond", "bourbon", "brown sugar", "caramel", "ethyl maltol", "hazelnut", "liquorice", "marshmallow", "milk", "rum", "sugar"] },
  { motif: "resin", names: ["labdanum", "elemi", "opium", "benzoin", "cistus absolute", "myrrh", "peru balsam resinoid"] },
  { motif: "fruit", names: ["blackcurrant", "raspberry", "melon", "coconut", "date", "fruity fresh top", "lychee", "mirabelle", "pear", "pomegranate", "red berries", "rhubarb", "strawberry"] },
  { motif: "fresh", names: ["aldehyde", "aquatic", "ozonic", "marine notes"] },
];

function motifFor(note: string): Motif {
  const normalized = note.toLocaleLowerCase("en-US");
  return MOTIFS.find(({ names }) =>
    names.some((name) => normalized.includes(name)),
  )?.motif ?? "abstract";
}

const paths: Record<Motif, ReactNode> = {
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
      <path d="M12 3c1.4 4.2 2.8 5.6 7 7-4.2 1.4-5.6 2.8-7 7-1.4-4.2-2.8-5.6-7-7 4.2-1.4 5.6-2.8 7-7Z" />
      <path d="M18.5 16.5l.6 1.4 1.4.6-1.4.6-.6 1.4-.6-1.4-1.4-.6 1.4-.6.6-1.4Z" />
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
      <path d="M8 20c1-7 3-13 8-17M11 20c.5-6 2-11 5-15" />
      <path d="M7 13c2 0 3 .8 4 2M13 9c2 0 3 .8 4 2" />
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
  return (
    <svg
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
      {paths[motifFor(note)]}
    </svg>
  );
}
