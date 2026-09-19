import catalog from "../../data/catalog.json";

import type { Product } from "@/lib/types";

type CatalogSlugRow = {
  product_id: string;
  title: string;
  brand?: string | null;
  attributes?: Record<string, string | undefined>;
};

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

const catalogSlugByProductId = new Map(
  (catalog.products as CatalogSlugRow[])
    .filter((product) => product.product_id.startsWith("SC-"))
    .map((product) => {
      const brand = String(product.brand || "").trim();
      const canonicalName = String(
        product.attributes?.canonical_name || product.title,
      ).trim();

      return [
        product.product_id,
        fragranceSlug(brand, canonicalName),
      ] as const;
    }),
);

export function fragrancePathForProduct(
  product: Pick<
    Product,
    "product_id" | "brand" | "title" | "attributes"
  >,
): string {
  const catalogSlug = catalogSlugByProductId.get(
    product.product_id,
  );

  if (catalogSlug) {
    return `/duft/${catalogSlug}`;
  }

  const brand = String(product.brand || "").trim();
  const name = String(
    product.attributes?.canonical_name || product.title,
  ).trim();

  return `/duft/${fragranceSlug(brand, name)}`;
}
