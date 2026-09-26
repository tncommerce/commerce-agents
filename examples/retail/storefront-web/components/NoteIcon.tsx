import type { ReactNode } from "react";

type Motif =
  | "bergamot"
  | "grapefruit"
  | "jasmine"
  | "patchouli"
  | "lavender"
  | "tonka"
  | "mandarin"
  | "lemon"
  | "geranium"
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
  { motif: "lavender", names: ["provençal lavender", "lavender"] },
  { motif: "tonka", names: ["tonka bean", "tonka"] },
  { motif: "mandarin", names: ["mandarin orange", "mandarin", "sicilian orange", "italian orange"] },
  { motif: "lemon", names: ["lemon", "citron"] },
  { motif: "geranium", names: ["geranium"] },
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
  { motif: "flower", names: ["orange blossom", "neroli", "violet", "rose", "iris", "orris", "magnolia", "carnation", "floral", "lily", "orchid", "mahonia"] },
  { motif: "citrus", names: ["orange", "lime", "citrus", "petit grain"] },
  { motif: "leaf", names: ["sage", "rosemary", "basil", "mint", "papyrus", "wormwood"] },
  { motif: "wood", names: ["akigalawood", "georgywood", "guaiac wood", "wood", "cedar", "cypress", "sandal", "birch", "oud", "cashmere", "cashmeran"] },
  { motif: "spice", names: ["ginger", "cardamom", "cinnamon", "nutmeg", "coriander", "spices"] },
  { motif: "sweet", names: ["praline", "chestnut", "coumarin"] },
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
  lavender: (
    <>
      <path d="M11.8 21V7.3M8.8 20.2l3-4.1M15.4 19.4l-3.6-4.2" stroke="#527241" strokeWidth="1.05" />
      <path d="M8.7 7.4c1.2-1.6 2.1-1.7 3-.7-1 1.4-2 1.7-3 .7ZM12 6.1c1.1-1.7 2.1-1.8 3-.9-.9 1.5-1.9 1.9-3 .9ZM9.6 10.2c1.2-1.6 2.2-1.7 3-.7-1 1.5-2 1.8-3 .7ZM12.4 9.2c1.2-1.7 2.2-1.7 3.1-.7-1 1.4-2.1 1.8-3.1.7ZM9.8 13.1c1.2-1.6 2.2-1.6 3-.6-1 1.4-2 1.7-3 .6ZM12.6 12.1c1.2-1.6 2.2-1.6 3-.6-1 1.4-2 1.7-3 .6Z" fill="#8C6CC1" stroke="#654B92" strokeWidth=".55" />
      <path d="M11.8 7.2c-.2-2.5.5-4 2-4.4 1.2 1.5.8 3.3-1.3 4.7" fill="#A786D4" stroke="#6A5198" strokeWidth=".65" />
    </>
  ),
  tonka: (
    <>
      <path d="M7.2 5.2c-3.1 3-3 8.3.2 13 1.3 1.9 3.1 2.6 4.5 1.1 1.8-2.1 1.7-7.5-.4-11.6-1.1-2.2-2.6-3.6-4.3-2.5Z" fill="#7A4A30" stroke="#4E2C20" strokeWidth=".85" />
      <path d="M15.6 4.4c-2.5 2.8-2.3 7.9.3 12.2 1.2 2 2.9 2.7 4.2 1.2 1.7-1.9 1.5-7-.3-10.8-1.1-2.3-2.6-3.8-4.2-2.6Z" fill="#9B6541" stroke="#5B3725" strokeWidth=".85" />
      <path d="M8.2 7.1c1.2 3.7 1.7 7.2 1.4 10.6M16.6 6.3c1 3.4 1.4 6.6 1.1 9.7" stroke="#C9966B" strokeWidth=".7" />
    </>
  ),
  mandarin: (
    <>
      <circle cx="12" cy="12" r="8.1" fill="#F29A34" stroke="#A95B22" strokeWidth=".9" />
      <circle cx="12" cy="12" r="5.5" fill="#FFB54A" stroke="#D77C28" strokeWidth=".7" />
      <circle cx="12" cy="12" r="1.05" fill="#F7D7A1" stroke="none" />
      <path d="M12 6.5v4.4M17.5 12h-4.4M12 17.5v-4.4M6.5 12h4.4M8.2 8.2l3.1 3.1M15.8 8.2l-3.1 3.1M15.8 15.8l-3.1-3.1M8.2 15.8l3.1-3.1" stroke="#FFE1A6" strokeWidth=".72" />
      <path d="M14.7 4.3c1.3-1.2 2.8-1.4 4.1-.8-.9 1.5-2.3 2.4-4 2.4" fill="#6D9A4B" stroke="#4D7534" strokeWidth=".72" />
    </>
  ),
  lemon: (
    <>
      <path d="M12 3.3c4.6 0 7.8 3.5 7.8 8.7S16.6 20.7 12 20.7 4.2 17.2 4.2 12 7.4 3.3 12 3.3Z" fill="#F2DF4A" stroke="#A69A28" strokeWidth=".9" />
      <path d="M7.4 11.8c1.8-2.8 4.2-4.7 7.4-5.6M7.4 12.2c1.8 2.8 4.2 4.7 7.4 5.6M12 5.8v12.4" stroke="#FFF5A7" strokeWidth=".75" />
      <path d="M15.2 3.8c1.2-1 2.5-1.1 3.7-.5-.8 1.4-2 2.1-3.6 2" fill="#78A455" stroke="#537A3B" strokeWidth=".7" />
    </>
  ),
  geranium: (
    <>
      <circle cx="12" cy="12" r="2" fill="#E5B44E" stroke="#A97B2E" strokeWidth=".65" />
      <path d="M12 9.8c-2.1-4.5-5.1-5.7-6.5-3.7-1.3 2 1.2 4.1 5.1 5M14.1 11.1c4.7-1.9 7.3-.2 6.6 2.1-.7 2.2-3.9 2-6.7-.2M12.8 14.1c2.2 4.5.2 7-2.1 6.4-2.3-.7-2.1-3.8.1-6.7M9.9 12.8c-4.6 2.2-7.1.2-6.4-2.1.7-2.2 3.8-2 6.7.1Z" fill="#D96C86" stroke="#9D465C" strokeWidth=".75" />
      <path d="M12.2 14.2c.4 2.9.1 5.2-.9 7" stroke="#4F7A43" strokeWidth=".85" />
      <path d="M11.4 17.3c-1.9-.5-3.2 0-4.1 1.2 1.4 1 2.8.9 4.2-.2M11.7 18.7c1.9-.4 3.3.2 4 1.4-1.5.9-2.9.7-4.1-.5" fill="#6B9858" stroke="#476F3B" strokeWidth=".55" />
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
      <rect x="4.6" y="8.2" width="14.8" height="8.5" rx="2.2" fill="#A76D3E" stroke="#654127" strokeWidth=".9" />
      <ellipse cx="18.3" cy="12.45" rx="2.5" ry="4.1" fill="#D39A61" stroke="#744A2D" strokeWidth=".75" />
      <ellipse cx="18.3" cy="12.45" rx="1.4" ry="2.5" fill="none" stroke="#9A643C" strokeWidth=".65" />
      <path d="M6.5 10.6c2.7.8 5.2.8 7.6-.1M6.4 13.1c2.7.7 5.1.7 7.4-.1M6.7 15.2c2.1.5 4.2.5 6.3 0" stroke="#D9A46F" strokeWidth=".65" />
      <path d="M7 7.9 9 5.4l2.4 2.7M11 8.1l2.2-3.2 2.4 3" fill="none" stroke="#7E5937" strokeWidth=".8" />
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
      <path d="M11 6.4c2.6-2.2 5.2-2.5 7.3-1.5" stroke="#557344" strokeWidth=".9" />
      <path d="M12.3 6.2c-1.1-1.7-2.4-2.4-4-2.2M15.4 5.4c.4-1.7 1.3-2.7 2.8-3.1" stroke="#6D8C53" strokeWidth=".65" />
      <circle cx="8.8" cy="9.1" r="2.45" fill="#CB7085" stroke="#8F4557" strokeWidth=".7" />
      <circle cx="15.4" cy="12.1" r="2.25" fill="#D98A96" stroke="#9C5967" strokeWidth=".7" />
      <circle cx="9.6" cy="16.2" r="2.05" fill="#B85D73" stroke="#824052" strokeWidth=".7" />
      <circle cx="15.8" cy="17.1" r="1.7" fill="#E0A1AB" stroke="#A86672" strokeWidth=".65" />
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
      <path d="M12 2.8 18.4 8l-2.2 9.1-4.2 4-4.3-4L5.6 8 12 2.8Z" fill="#E4A73C" stroke="#9B6A24" strokeWidth=".9" />
      <path d="m7.7 8.6 4.3 2.5 4.4-2.4-1.7 7-2.7 2.6-2.8-2.6-1.5-7.1Z" fill="#F1C55F" stroke="none" opacity=".92" />
      <path d="M9.2 7.2 12 5l2.8 2.2M9.7 14.3h4.7" stroke="#FFF0A4" strokeWidth=".75" />
      <circle cx="14.9" cy="6.9" r=".9" fill="#FFF7C8" stroke="none" />
    </>
  ),
  musk: (
    <>
      <circle cx="12" cy="12" r="7.6" fill="#F4EFE8" stroke="#B8A99D" strokeWidth=".8" />
      <circle cx="12" cy="12" r="5.25" fill="#E8DFE4" stroke="#C6B3BF" strokeWidth=".7" />
      <path d="M12 6.8c2.2 1.8 3.6 3.7 3.6 5.7a3.6 3.6 0 0 1-7.2 0c0-2 1.4-3.9 3.6-5.7Z" fill="#FFFDF8" stroke="#B59EAA" strokeWidth=".7" />
      <circle cx="12" cy="12.7" r="1.35" fill="#D1B3C2" stroke="none" />
      <path d="M7.1 7.5c-1.1-.7-2.1-.5-2.9.6M16.9 7.5c1.1-.7 2.1-.5 2.9.6M6.6 16.8c-.9.6-1.3 1.5-1.1 2.6M17.4 16.8c.9.6 1.3 1.5 1.1 2.6" stroke="#D7C8D0" strokeWidth=".65" />
    </>
  ),
  leather: (
    <>
      <path d="M6 5c2 1 4 1 6 0 2 1 4 1 6 0l1 14c-5-2-9-2-14 0L6 5Z" fill="#8B5A3B" stroke="#5B3827" strokeWidth=".9" />
      <path d="M8.3 8.1c2.5 1 4.9 1 7.4 0M8.1 11.1c2.6.8 5.2.8 7.8 0M7.9 14.3c2.7.7 5.4.7 8.1 0" stroke="#B98461" strokeWidth=".65" />
      <path d="M7.3 17.2c3.2-.9 6.4-.9 9.5 0" stroke="#D2A07A" strokeWidth=".65" />
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
      <path d="M12 8c-4-3-8 0-7 5 1 5 4 8 7 6 3 2 6-1 7-6 1-5-3-8-7-5Z" fill="#80B94C" stroke="#4F7E32" strokeWidth=".9" />
      <path d="M12 7c0-2 1-4 3-5" stroke="#6E4D2E" strokeWidth="1.1" />
      <path d="M12.2 5.7c-2.2-2-4.2-1.8-5.7-.5 1.7 1.7 3.7 2.1 5.8 1.2" fill="#5F9443" stroke="#477433" strokeWidth=".65" />
      <path d="M8.1 11.4c1.1-1.4 2.3-1.8 3.6-1.3" stroke="#CDE9A0" strokeWidth=".65" />
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
      <path d="M6 19h12M8 16h8l1 3H7l1-3Z" fill="#9A6B43" stroke="#65462F" strokeWidth=".8" />
      <path d="M9 16h6l-.8-2.2h-4.4L9 16Z" fill="#C28E57" stroke="none" />
      <path d="M12 15c-3-3 2-4 0-7-1-1-1-3 1-5M9 14c-2-2 1-3 0-5M15 13c2-2-.6-3.1.6-5.2" stroke="#B7A6C9" strokeWidth=".9" />
      <path d="M11.9 3.4c1.1.5 1.6 1.3 1.4 2.5" stroke="#D5C9E2" strokeWidth=".65" />
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
