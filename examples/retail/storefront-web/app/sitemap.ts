import type { MetadataRoute } from "next";

import { LIVE_FRAGRANCES } from "@/lib/fragranceCatalog";
import { SITE_URL } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const staticRoutes: MetadataRoute.Sitemap = [
    {
      url: SITE_URL,
      changeFrequency: "weekly",
      priority: 1,
    },
    {
      url: `${SITE_URL}/transparenz`,
      changeFrequency: "monthly",
      priority: 0.3,
    },
    {
      url: `${SITE_URL}/impressum`,
      changeFrequency: "monthly",
      priority: 0.2,
    },
    {
      url: `${SITE_URL}/datenschutz`,
      changeFrequency: "monthly",
      priority: 0.2,
    },
  ];

  const fragranceRoutes: MetadataRoute.Sitemap =
    LIVE_FRAGRANCES.map((fragrance) => ({
      url: `${SITE_URL}/duft/${fragrance.slug}`,
      changeFrequency: "weekly",
      priority: 0.7,
    }));

  return [...staticRoutes, ...fragranceRoutes];
}
