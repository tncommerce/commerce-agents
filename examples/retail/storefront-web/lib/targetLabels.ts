const TARGET_LABELS: Record<string, string> = {
  men: "Herren",
  women: "Damen",
  unisex: "Unisex",
};

export function targetLabel(value: string): string {
  return TARGET_LABELS[value.toLowerCase()] || value;
}
