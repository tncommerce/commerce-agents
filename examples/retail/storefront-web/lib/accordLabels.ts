const ACCORD_LABELS: Record<string, string> = {
  fresh: "Frisch",
  citrus: "Zitrisch",
  chypre: "Chypre",
  aquatic: "Aquatisch",
  green: "Grün",
  spicy: "Würzig",
  sweet: "Süß",
  synthetic: "Synthetisch",
  "white floral": "Weißblumig",
  fruity: "Fruchtig",
  woody: "Holzig",
  smoky: "Rauchig",
  powdery: "Pudrig",
  floral: "Blumig",
  creamy: "Cremig",
  gourmand: "Gourmand",
  oriental: "Orientalisch",
  aromatic: "Aromatisch",
  leathery: "Ledrig",
  resinous: "Harzig",
};

export function accordLabel(value: string): string {
  return ACCORD_LABELS[value.toLowerCase()] || value;
}
