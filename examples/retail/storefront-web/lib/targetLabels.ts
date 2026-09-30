import { catalogAudienceFor } from "@/lib/fragranceCatalog";

const TARGET_LABELS: Record<string, string> = {
  men: "Herren",
  women: "Damen",
  unisex: "Unisex",
};

export function targetLabel(value: string): string {
  return TARGET_LABELS[value.toLowerCase()] || value;
}

/** Show the same exclusive audience as the catalog filters. */
export function targetGroupLabel(values: readonly string[]): string {
  const groups = values.map((value) => {
    const normalized = value.trim().toLowerCase();
    return normalized === "herren" ? "men" : normalized === "damen" ? "women" : normalized;
  });
  const audience = catalogAudienceFor(groups);
  return audience ? targetLabel(audience) : values.map(targetLabel).join(", ");
}
