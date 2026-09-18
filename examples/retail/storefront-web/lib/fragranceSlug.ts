import type { Product } from "@/lib/types";

export function slugifyFragrance(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[’']/g, "")
    .replace(/&/g, " und ")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function fragranceSlug(
  brand: string,
  name: string,
): string {
  return slugifyFragrance(`${brand} ${name}`);
}

export function fragrancePathForProduct(
  product: Pick<Product, "brand" | "title" | "attributes">,
): string {
  const brand = String(product.brand || "").trim();
  const name = String(
    product.attributes?.canonical_name || product.title,
  ).trim();

  return `/duft/${fragranceSlug(brand, name)}`;
}
